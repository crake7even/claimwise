"""检索评测：对评测集逐题检索，计算 Hit@1 / Recall@5 / MRR@10，并输出 Markdown 报告与 JSON 摘要。

默认离线运行（关闭 ES、Embedding、Tavily），只评测本地 BM25，不需要任何 API Key。

用法：
  python eval/run_eval.py                      # dev 集，离线
  python eval/run_eval.py --split all          # dev + holdout
  python eval/run_eval.py --online --mode semantic   # 使用 .env 中配置的 ES / Embedding
  python eval/run_eval.py --baseline eval/reports/<基线>.json   # 与基线对比
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = BACKEND_DIR / "eval"
sys.path.insert(0, str(BACKEND_DIR))

MODE_FLAGS = {
    "quick": (True, False),
    "semantic": (True, True),
}
SEARCH_DEPTH = 10


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def git_branch() -> str:
    try:
        output = subprocess.run(
            ["git", "-C", str(BACKEND_DIR), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return output.replace("/", "-") or "unknown"
    except Exception:
        return "unknown"


def chunk_matches(context: dict, source: dict) -> bool:
    if Path(context["file_name"]).stem != source["file"]:
        return False
    content = normalize(context["content"])
    return all(normalize(keyword) in content for keyword in source["keywords"])


def evaluate_row(row: dict, contexts: list[dict]) -> dict:
    sources = row["expected_sources"]
    first_rank = None
    found_at: list[int | None] = []
    for source in sources:
        rank = next((i for i, ctx in enumerate(contexts, start=1) if chunk_matches(ctx, source)), None)
        found_at.append(rank)
    for i, ctx in enumerate(contexts, start=1):
        if any(chunk_matches(ctx, source) for source in sources):
            first_rank = i
            break
    hit1 = first_rank == 1
    recall5 = all(rank is not None and rank <= 5 for rank in found_at)
    return {
        "hit1": hit1,
        "recall5": recall5,
        "mrr": 1.0 / first_rank if first_rank else 0.0,
        "first_rank": first_rank,
        "found_at": found_at,
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="ClaimWise 检索评测")
    parser.add_argument("--dataset", default=str(EVAL_DIR / "dataset.jsonl"))
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    parser.add_argument("--mode", choices=sorted(MODE_FLAGS), default="quick")
    parser.add_argument("--online", action="store_true", help="使用 .env 中的 ES / Embedding 配置")
    parser.add_argument("--baseline", help="基线 JSON 摘要路径，用于对比")
    parser.add_argument("--name", help="报告文件名（默认：日期-分支-模式）")
    args = parser.parse_args()

    if not args.online:
        os.environ.update({"ENABLE_ES": "false", "ENABLE_EMBEDDING": "false", "DASHSCOPE_API_KEY": "", "TAVILY_API_KEY": ""})

    from rag_upgrade import HybridRagService

    rows = [json.loads(line) for line in Path(args.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.split != "all":
        rows = [row for row in rows if row["split"] == args.split]

    service = HybridRagService()
    use_es, use_embedding = MODE_FLAGS[args.mode]

    results: list[dict] = []
    for row in rows:
        started = time.perf_counter()
        response = service.search(
            row["question"], top_k=SEARCH_DEPTH,
            use_es=use_es, use_embedding=use_embedding, use_external=False,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        contexts = response["contexts"]
        top_score = contexts[0]["merged_score"] if contexts else 0.0
        item = {
            "id": row["id"],
            "category": row["category"],
            "question": row["question"],
            "top_score": round(top_score, 4),
            "latency_ms": round(latency_ms, 2),
            "top3": [f"{Path(c['file_name']).stem}#{c['chunk_id']}" for c in contexts[:3]],
            "expected": [s["file"] + ":" + "/".join(s["keywords"]) for s in row["expected_sources"]],
        }
        if row["category"] != "out_of_scope":
            item.update(evaluate_row(row, contexts))
        results.append(item)

    scored = [r for r in results if "hit1" in r]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        by_category[r["category"]].append(r)

    def metrics(items: list[dict]) -> dict:
        return {
            "n": len(items),
            "hit1": round(mean([float(r["hit1"]) for r in items]), 4),
            "recall5": round(mean([float(r["recall5"]) for r in items]), 4),
            "mrr10": round(mean([r["mrr"] for r in items]), 4),
        }

    in_scope_scores = [r["top_score"] for r in scored]
    oos_scores = [r["top_score"] for r in results if r["category"] == "out_of_scope"]
    latencies = [r["latency_ms"] for r in results]
    summary = {
        "name": args.name or f"{date.today().isoformat()}-{git_branch()}-{args.mode}{'-online' if args.online else ''}",
        "split": args.split,
        "mode": args.mode,
        "online": args.online,
        "retrievers": service.status(),
        "overall": metrics(scored),
        "by_category": {cat: metrics(items) for cat, items in sorted(by_category.items())},
        "score_distribution": {
            "in_scope_top1": {"p10": percentile(in_scope_scores, 10), "median": percentile(in_scope_scores, 50)},
            "out_of_scope_top1": {"median": percentile(oos_scores, 50), "p90": percentile(oos_scores, 90), "n": len(oos_scores)},
        },
        "latency_ms": {"p50": round(percentile(latencies, 50), 2), "p95": round(percentile(latencies, 95), 2)},
    }

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))["summary"] if args.baseline else None
    reports_dir = EVAL_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"{summary['name']}.json"
    md_path = reports_dir / f"{summary['name']}.md"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(summary, results, baseline), encoding="utf-8")

    overall = summary["overall"]
    print(f"[{summary['name']}] n={overall['n']} Hit@1={overall['hit1']:.3f} Recall@5={overall['recall5']:.3f} MRR@10={overall['mrr10']:.3f}")
    print(f"报告：{md_path.relative_to(BACKEND_DIR)}")
    return 0


def fmt_delta(value: float, base: float | None) -> str:
    if base is None:
        return f"{value:.3f}"
    delta = value - base
    sign = "+" if delta >= 0 else ""
    return f"{value:.3f}（{sign}{delta:.3f}）"


def render_markdown(summary: dict, results: list[dict], baseline: dict | None) -> str:
    lines = [
        f"# 检索评测报告：{summary['name']}",
        "",
        f"- split：`{summary['split']}`；mode：`{summary['mode']}`；online：`{summary['online']}`",
        f"- 检索器状态：`{json.dumps({k: v for k, v in summary['retrievers'].items() if k != 'docs_dir'}, ensure_ascii=False)}`",
        f"- 对比基线：`{baseline['name']}`" if baseline else "- 对比基线：无",
        "",
        "## 总体与分题型",
        "",
        "| 题型 | n | Hit@1 | Recall@5 | MRR@10 |",
        "|---|---|---|---|---|",
    ]
    rows = [("overall", summary["overall"])] + list(summary["by_category"].items())
    for name, m in rows:
        base = None
        if baseline:
            base = baseline["overall"] if name == "overall" else baseline["by_category"].get(name)
        lines.append(
            f"| {name} | {m['n']} | {fmt_delta(m['hit1'], base and base['hit1'])} | "
            f"{fmt_delta(m['recall5'], base and base['recall5'])} | {fmt_delta(m['mrr10'], base and base['mrr10'])} |"
        )

    dist = summary["score_distribution"]
    lines += [
        "",
        "## Top-1 分数分布（供低置信拒答阈值参考）",
        "",
        f"- 库内题 Top-1：P10 = {dist['in_scope_top1']['p10']:.3f}，中位数 = {dist['in_scope_top1']['median']:.3f}",
        f"- 库外题 Top-1（n={dist['out_of_scope_top1']['n']}）：中位数 = {dist['out_of_scope_top1']['median']:.3f}，P90 = {dist['out_of_scope_top1']['p90']:.3f}",
        f"- 检索延迟：P50 = {summary['latency_ms']['p50']} ms，P95 = {summary['latency_ms']['p95']} ms",
        "",
        "## 失败样本（Recall@5 未命中）",
        "",
        "| ID | 题型 | 问题 | 期望 | 首次命中排名 | 实际 Top-3 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        if "recall5" in r and not r["recall5"]:
            lines.append(
                f"| {r['id']} | {r['category']} | {r['question']} | {'<br>'.join(r['expected'])} | "
                f"{r['first_rank'] or '-'} | {'<br>'.join(r['top3'])} |"
            )
    lines += [
        "",
        "## 库外题 Top-1",
        "",
        "| ID | 问题 | Top-1 分数 | Top-1 |",
        "|---|---|---|---|",
    ]
    for r in results:
        if r["category"] == "out_of_scope":
            lines.append(f"| {r['id']} | {r['question']} | {r['top_score']:.3f} | {r['top3'][0] if r['top3'] else '-'} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
