from __future__ import annotations

from math import log2
import json

from .config import DATA_DIR, REPORT_DIR
from .search_service import CommerceSearchService


EVAL_PATH = DATA_DIR / "evaluation_queries.json"
REPORT_MD = REPORT_DIR / "search_evaluation.md"
REPORT_JSON = REPORT_DIR / "search_evaluation.json"


def _text(result: dict) -> str:
    return " ".join([
        result.get("name", ""),
        result.get("brand", ""),
        " ".join(result.get("categories", [])),
        " ".join(result.get("recall_sources", [])),
        result.get("rerank_reason", ""),
    ]).lower()


def is_relevant(result: dict, relevant_terms: list[str], expected_category: str) -> bool:
    text = _text(result)
    term_hit = any(term.lower() in text for term in relevant_terms)
    category_hit = expected_category.lower() in " ".join(result.get("categories", [])).lower()
    return term_hit or category_hit


def recall_at_k(results: list[dict], relevant_terms: list[str], expected_category: str, k: int) -> float:
    top_k = results[:k]
    hits = sum(1 for result in top_k if is_relevant(result, relevant_terms, expected_category))
    total_relevant = sum(1 for result in results if is_relevant(result, relevant_terms, expected_category))
    return hits / min(k, total_relevant) if total_relevant else 0.0


def ndcg_at_k(results: list[dict], relevant_terms: list[str], expected_category: str, k: int) -> float:
    dcg = 0.0
    for rank, result in enumerate(results[:k], start=1):
        rel = 1 if is_relevant(result, relevant_terms, expected_category) else 0
        dcg += rel / log2(rank + 1)
    ideal_hits = min(k, sum(1 for result in results if is_relevant(result, relevant_terms, expected_category)))
    idcg = sum(1 / log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def mrr_at_k(results: list[dict], relevant_terms: list[str], expected_category: str, k: int) -> float:
    for rank, result in enumerate(results[:k], start=1):
        if is_relevant(result, relevant_terms, expected_category):
            return 1 / rank
    return 0.0


def evaluate() -> dict:
    service = CommerceSearchService()
    queries = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    rows = []
    modes = ["keyword", "semantic", "hybrid_rerank"]

    for item in queries:
        row = {
            "query": item["query"],
            "expected_intent": item["intent"],
            "expected_category": item["expected_category"],
        }
        for mode in modes:
            output = service.search(item["query"], top_k=50, mode=mode)
            results = output["results"]
            row[f"{mode}_intent"] = output["intent"]["intent"]
            row[f"{mode}_recall_at_5"] = recall_at_k(results, item["relevant_terms"], item["expected_category"], 5)
            row[f"{mode}_ndcg_at_5"] = ndcg_at_k(results, item["relevant_terms"], item["expected_category"], 5)
            row[f"{mode}_mrr_at_5"] = mrr_at_k(results, item["relevant_terms"], item["expected_category"], 5)
            row[f"{mode}_top1"] = results[0]["name"] if results else ""
        rows.append(row)

    summary = {}
    for mode in modes:
        summary[mode] = {
            "recall_at_5": sum(row[f"{mode}_recall_at_5"] for row in rows) / len(rows),
            "ndcg_at_5": sum(row[f"{mode}_ndcg_at_5"] for row in rows) / len(rows),
            "mrr_at_5": sum(row[f"{mode}_mrr_at_5"] for row in rows) / len(rows),
        }

    return {
        "dataset": service.search("phone", top_k=1)["dataset"],
        "summary": summary,
        "rows": rows,
    }


def write_report(report: dict) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Ecommerce Search Strategy Evaluation",
        "",
        "This report compares three retrieval/ranking paths on a small hand-labeled ecommerce query set.",
        "",
        "## Dataset Profile",
        "",
        f"- Products: {report['dataset']['count']}",
        f"- Price range: {report['dataset']['price']['min']} - {report['dataset']['price']['max']}, avg {report['dataset']['price']['avg']}",
        f"- Top level categories: {', '.join(f'{name}({count})' for name, count in report['dataset']['top_level_categories'][:6])}",
        "",
        "## Metric Summary",
        "",
        "| Mode | Recall@5 | NDCG@5 | MRR@5 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for mode, metrics in report["summary"].items():
        lines.append(
            f"| {mode} | {metrics['recall_at_5']:.3f} | {metrics['ndcg_at_5']:.3f} | {metrics['mrr_at_5']:.3f} |"
        )

    lines.extend([
        "",
        "## Query Cases",
        "",
        "| Query | Expected Intent | Hybrid Intent | Keyword R@5 | Semantic R@5 | Hybrid R@5 | Hybrid Top1 |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ])
    for row in report["rows"]:
        lines.append(
            f"| {row['query']} | {row['expected_intent']} | {row['hybrid_rerank_intent']} | "
            f"{row['keyword_recall_at_5']:.2f} | {row['semantic_recall_at_5']:.2f} | "
            f"{row['hybrid_rerank_recall_at_5']:.2f} | {row['hybrid_rerank_top1']} |"
        )

    lines.extend([
        "",
        "## Interview Notes",
        "",
        "- Keyword/BM25 is the baseline recall path and is strong on exact product terms.",
        "- Semantic expansion improves long-tail and scenario queries, but must be guarded by category and business features.",
        "- Hybrid rerank combines relevance, category match, price/promotion intent, popularity, sales, and rating.",
        "- The current labels are a small offline proxy. A production version should use search logs, clicks, add-to-cart, conversion, and A/B testing.",
    ])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    result = evaluate()
    write_report(result)
    print(f"Wrote {REPORT_MD}")
