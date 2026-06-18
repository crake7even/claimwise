from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
import re

from .document_loader import DocChunk


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]{1,4}")


@dataclass
class RetrievalHit:
    source: str
    file_name: str
    chunk_id: int
    content: str
    score: float
    retriever: str

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "file_name": self.file_name,
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": round(float(self.score), 4),
            "retriever": self.retriever,
        }


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    raw_tokens = TOKEN_RE.findall(lowered)
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.append(token)
        if any("\u4e00" <= char <= "\u9fff" for char in token) and len(token) > 1:
            tokens.extend(token[i:i + 2] for i in range(len(token) - 1))
    return tokens


class BM25Retriever:
    def __init__(self, chunks: list[DocChunk]):
        self.chunks = chunks
        self.tokenized_docs = [tokenize(chunk.content) for chunk in chunks]
        self.doc_freq = Counter()
        for tokens in self.tokenized_docs:
            self.doc_freq.update(set(tokens))
        self.avg_doc_len = (
            sum(len(tokens) for tokens in self.tokenized_docs) / max(len(self.tokenized_docs), 1)
        )

    def score(self, query_tokens: list[str], doc_tokens: list[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        counts = Counter(doc_tokens)
        total_docs = len(self.tokenized_docs)
        k1 = 1.5
        b = 0.75
        score = 0.0
        for token in query_tokens:
            df = self.doc_freq.get(token, 0)
            if df <= 0:
                continue
            idf = log(1 + (total_docs - df + 0.5) / (df + 0.5))
            tf = counts[token]
            denom = tf + k1 * (1 - b + b * len(doc_tokens) / max(self.avg_doc_len, 1))
            score += idf * (tf * (k1 + 1)) / max(denom, 1e-9)
        return score

    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        query_tokens = tokenize(query)
        hits: list[RetrievalHit] = []
        for chunk, doc_tokens in zip(self.chunks, self.tokenized_docs):
            score = self.score(query_tokens, doc_tokens)
            if score <= 0:
                continue
            hits.append(RetrievalHit(
                source=chunk.source,
                file_name=chunk.file_name,
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=score,
                retriever="local_bm25",
            ))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]
