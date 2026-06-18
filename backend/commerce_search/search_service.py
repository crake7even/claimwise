from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from math import log
import json
from typing import Iterable

from .data_loader import load_products, dataset_profile
from .query_intent import QueryIntent, analyze_query, tokenize
from .qwen_enhancer import enhance_query_with_qwen


@dataclass
class SearchResult:
    id: str
    name: str
    brand: str
    categories: list[str]
    price: float
    image: str
    popularity: float
    sales: float
    rating: float
    promotion: bool
    keyword_score: float
    semantic_score: float
    business_score: float
    final_score: float
    recall_sources: list[str]
    rerank_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class CommerceSearchService:
    def __init__(self, products: list[dict] | None = None):
        self.products = products or load_products()
        self._documents = [self._product_text(product) for product in self.products]
        self._tokenized_docs = [tokenize(text) for text in self._documents]
        self._doc_freq = self._build_doc_freq(self._tokenized_docs)
        self._avg_doc_len = sum(len(doc) for doc in self._tokenized_docs) / max(len(self._tokenized_docs), 1)
        self._max_popularity = max(float(p.get("popularity", 0)) for p in self.products) or 1.0
        self._max_sales = max(float(p.get("sales", 0)) for p in self.products) or 1.0

    @staticmethod
    def _product_text(product: dict) -> str:
        return " ".join([
            product.get("name", ""),
            product.get("description", ""),
            product.get("brand", ""),
            " ".join(product.get("categories", [])),
            " ".join(product.get("tags", [])),
        ]).lower()

    @staticmethod
    def _build_doc_freq(tokenized_docs: Iterable[list[str]]) -> Counter:
        doc_freq = Counter()
        for tokens in tokenized_docs:
            doc_freq.update(set(tokens))
        return doc_freq

    def _bm25_score(self, query_tokens: list[str], doc_tokens: list[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        counts = Counter(doc_tokens)
        total_docs = len(self._tokenized_docs)
        k1 = 1.5
        b = 0.75
        score = 0.0
        for token in query_tokens:
            df = self._doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = log(1 + (total_docs - df + 0.5) / (df + 0.5))
            tf = counts[token]
            denom = tf + k1 * (1 - b + b * len(doc_tokens) / max(self._avg_doc_len, 1))
            score += idf * (tf * (k1 + 1)) / denom
        return score

    def _field_score(self, intent: QueryIntent, product: dict) -> float:
        name = product.get("name", "").lower()
        brand = product.get("brand", "").lower()
        description = product.get("description", "").lower()
        categories = " ".join(product.get("categories", [])).lower()
        tags = " ".join(product.get("tags", [])).lower()
        score = 0.0
        for token in intent.tokens:
            if token in name:
                score += 4.0
            if token in brand:
                score += 3.5
            if token in categories:
                score += 2.5
            if token in tags:
                score += 2.0
            if token in description:
                score += 1.0
        return score

    def _semantic_score(self, intent: QueryIntent, product: dict) -> float:
        text = self._product_text(product)
        score = self._field_score(intent, product)
        for term in intent.expanded_terms:
            term_l = term.lower()
            if term_l in text:
                score += 1.8
        if intent.intent == "scenario_need":
            category_text = " ".join(product.get("categories", [])).lower()
            if any(token in category_text for token in intent.tokens):
                score += 2.0
        return score

    def _business_score(self, intent: QueryIntent, product: dict) -> float:
        popularity = float(product.get("popularity", 0)) / self._max_popularity
        sales = float(product.get("sales", 0)) / self._max_sales
        rating = float(product.get("rating", 0)) / 5.0
        price = float(product.get("price", 0))
        score = popularity * 1.2 + sales * 1.0 + rating * 0.8
        if intent.filters.get("promotion") and product.get("promotion"):
            score += 1.2
        if intent.filters.get("price_bias") == "low":
            if price <= 30:
                score += 1.5
            elif price <= 100:
                score += 0.6
            else:
                score -= 0.4
        return score

    def _recall_sources(self, keyword: float, semantic: float, product: dict, intent: QueryIntent) -> list[str]:
        sources = []
        if keyword > 0:
            sources.append("keyword_bm25")
        if semantic > keyword:
            sources.append("semantic_expansion")
        if intent.filters.get("promotion") and product.get("promotion"):
            sources.append("promotion_filter")
        if not sources:
            sources.append("business_fallback")
        return sources

    @staticmethod
    def _reason(intent: QueryIntent, product: dict, keyword: float, semantic: float, business: float) -> str:
        category = " > ".join(product.get("categories", [])[:2])
        parts = []
        if keyword > 0:
            parts.append("query terms matched product fields")
        if semantic > keyword:
            parts.append("expanded terms improved semantic match")
        if intent.filters.get("price_bias") == "low":
            parts.append("low-price intent considered")
        if intent.filters.get("promotion") and product.get("promotion"):
            parts.append("promotion intent matched")
        if business > 1.5:
            parts.append("popularity/sales/rating boosted")
        if not parts:
            parts.append("kept as fallback candidate")
        return f"{'; '.join(parts)}; category={category}"

    def search(self, query: str, top_k: int = 10, mode: str = "hybrid_rerank", use_qwen: bool = False) -> dict:
        qwen = enhance_query_with_qwen(query) if use_qwen else {"enabled": False, "reason": "disabled by default"}
        intent = analyze_query(query)
        results: list[SearchResult] = []
        for index, product in enumerate(self.products):
            keyword = self._bm25_score(intent.tokens, self._tokenized_docs[index]) + self._field_score(intent, product)
            semantic = self._semantic_score(intent, product)
            business = self._business_score(intent, product)
            if mode == "keyword":
                final = keyword
            elif mode == "semantic":
                final = semantic
            else:
                final = keyword * 1.0 + semantic * 1.3 + business * 0.8
            results.append(SearchResult(
                id=str(product.get("id")),
                name=product.get("name", ""),
                brand=product.get("brand", ""),
                categories=product.get("categories", []),
                price=float(product.get("price", 0)),
                image=product.get("image", ""),
                popularity=float(product.get("popularity", 0)),
                sales=float(product.get("sales", 0)),
                rating=float(product.get("rating", 0)),
                promotion=bool(product.get("promotion")),
                keyword_score=round(keyword, 4),
                semantic_score=round(semantic, 4),
                business_score=round(business, 4),
                final_score=round(final, 4),
                recall_sources=self._recall_sources(keyword, semantic, product, intent),
                rerank_reason=self._reason(intent, product, keyword, semantic, business),
            ))
        results.sort(key=lambda item: item.final_score, reverse=True)
        return {
            "query": query,
            "mode": mode,
            "qwen_enhancement": qwen,
            "intent": intent.to_dict(),
            "dataset": dataset_profile(self.products),
            "results": [result.to_dict() for result in results[:top_k]],
        }


def search(query: str, top_k: int = 10, mode: str = "hybrid_rerank", use_qwen: bool = False) -> dict:
    return CommerceSearchService().search(query=query, top_k=top_k, mode=mode, use_qwen=use_qwen)


if __name__ == "__main__":
    import argparse
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--mode", choices=["keyword", "semantic", "hybrid_rerank"], default="hybrid_rerank")
    parser.add_argument("--use-qwen", action="store_true")
    args = parser.parse_args()
    print(json.dumps(search(args.query, args.top_k, args.mode, args.use_qwen), ensure_ascii=False, indent=2))
