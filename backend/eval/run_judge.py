"""生成质量评测（LLM-judge）：用线上同一条链路生成回答，再由更强的模型按关键点打分。

指标：
- 关键点覆盖率：key_points 中被回答覆盖的比例（库内题）
- 忠实度：回答中的事实陈述能否由提供给模型的资料支撑（库内题）
- 库外处理准确率：库外题明确说明资料不足，或覆盖了 key_points 描述的期望处理方式（覆盖率 >= 0.5）

用法：
  python eval/run_judge.py --mode semantic --limit 40          # dev 集前 40 题
  python eval/run_judge.py --mode semantic --split holdout
需要 DASHSCOPE_API_KEY；裁判模型由 EVAL_JUDGE_MODEL 指定（默认 qwen3.8-max）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = BACKEND_DIR / "eval"
sys.path.insert(0, str(BACKEND_DIR))

# 失败样本占比超过该值时整次评测视为无效（通常是网络或接口故障），避免用残缺样本得出结论
MAX_FAILED_RATIO = 0.05

JUDGE_PROMPT = """你是严格的保险问答评测员。根据【参考资料】评估【回答】，只输出 JSON，不要输出其他内容。

字段：
- "covered": 数组，与【关键点】一一对应，每项为 true/false，表示回答是否表达了该关键点的含义（措辞可以不同）。
- "faithful": true/false，回答中的事实性陈述（金额、比例、期限、是否赔付等）是否都能由【参考资料】支撑；资料里没有却被断言的内容判为 false。
- "refused": true/false，回答是否明确表示资料中没有相关信息 / 无法回答 / 以保单为准，而不是给出具体结论。
- "reason": 不超过 60 字的简要说明。"""


def load_rows(split: str, limit: int | None, ids: list[str] | None) -> list[dict]:
    rows = [json.loads(line) for line in (EVAL_DIR / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if split != "all":
        rows = [row for row in rows if row["split"] == split]
    if ids:
        rows = [row for row in rows if row["id"] in ids]
    return rows[:limit] if limit else rows


def oos_handled(result: dict) -> bool:
    return result["refused"] or result["coverage"] >= 0.5


def generate(api_server, row: dict, mode: str) -> dict:
    raw = "".join(api_server.stream_answer(row["question"], mode))
    if not hasattr(api_server, "retrieve"):
        return generate_legacy(api_server, row, mode, raw)
    text, sources, errors = "", [], []
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event["type"] == "sources":
            sources = event["sources"]
        elif event["type"] == "delta":
            text += event["text"]
        elif event["type"] == "error":
            errors.append(event["message"])
    return {"answer": text, "sources": sources, "errors": errors}


def generate_legacy(api_server, row: dict, mode: str, answer: str) -> dict:
    """兼容改造前的版本（纯文本流、不返回来源）：参考资料取自其自身的检索结果，用于基线对比。"""
    result = api_server.service.search(
        query=row["question"], top_k=6, use_es=True, use_embedding=mode == "semantic", use_external=False,
    )
    sources = [{"id": i, "title": item["file_name"], "section": "", "snippet": item["content"]}
               for i, item in enumerate(result["contexts"], start=1)]
    return {"answer": answer, "sources": sources, "errors": []}


def judge(client, model: str, row: dict, generated: dict) -> dict:
    references = "\n\n".join(f"[{s['id']}] {s['title']} {s.get('section', '')}\n{s['snippet'][:1200]}" for s in generated["sources"])
    key_points = "\n".join(f"{i}. {point}" for i, point in enumerate(row["key_points"], start=1))
    content = (
        f"【问题】{row['question']}\n\n【关键点】\n{key_points}\n\n"
        f"【参考资料】\n{references or '（无）'}\n\n【回答】\n{generated['answer']}"
    )
    verdict: dict = {}
    for attempt in range(2):  # 裁判偶发输出非法 JSON（如未转义引号），重试一次
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": content}],
            temperature=0,
            response_format={"type": "json_object"},
            extra_body={"enable_thinking": False},
        )
        raw = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", raw, re.S)
        try:
            verdict = json.loads(match.group(0)) if match else {}
            break
        except json.JSONDecodeError:
            if attempt == 1:
                raise
    covered = [bool(item) for item in verdict.get("covered", [])][: len(row["key_points"])]
    covered += [False] * (len(row["key_points"]) - len(covered))
    return {
        "coverage": sum(covered) / len(covered) if covered else 0.0,
        "covered": covered,
        "faithful": bool(verdict.get("faithful")),
        "refused": bool(verdict.get("refused")),
        "reason": str(verdict.get("reason", ""))[:120],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ClaimWise 生成质量评测（LLM-judge）")
    parser.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    parser.add_argument("--mode", choices=["quick", "semantic"], default="semantic")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", help="逗号分隔的题目 ID，只评这些题")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--name", help="报告文件名")
    args = parser.parse_args()

    import api_server
    from openai import OpenAI

    if api_server.qwen_client() is None:
        print("需要 DASHSCOPE_API_KEY", file=sys.stderr)
        return 1
    judge_model = os.getenv("EVAL_JUDGE_MODEL", "qwen3.8-max")
    client = OpenAI(
        api_key=os.environ["DASHSCOPE_API_KEY"],
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )
    rows = load_rows(args.split, args.limit, args.ids.split(",") if args.ids else None)

    def run(row: dict) -> dict:
        try:
            generated = generate(api_server, row, args.mode)
            verdict = judge(client, judge_model, row, generated)
        except Exception as exc:
            return {"id": row["id"], "category": row["category"], "question": row["question"], "failed": f"{type(exc).__name__}: {exc}"}
        return {"id": row["id"], "category": row["category"], "question": row["question"],
                "should_refuse": row["should_refuse"], **generated, **verdict}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run, rows))

    ok = [r for r in results if "failed" not in r]
    in_scope = [r for r in ok if not r["should_refuse"]]
    oos = [r for r in ok if r["should_refuse"]]
    mean = lambda values: round(sum(values) / len(values), 4) if values else 0.0  # noqa: E731
    by_category: dict[str, list[dict]] = defaultdict(list)
    for r in in_scope:
        by_category[r["category"]].append(r)
    summary = {
        "name": args.name or f"judge-{date.today().isoformat()}-{args.split}-{args.mode}",
        "mode": args.mode,
        "split": args.split,
        "judge_model": judge_model,
        "chat_model": os.getenv("QWEN_CHAT_MODEL", "qwen3.6-flash"),
        "n": len(results),
        "failed": len(results) - len(ok),
        "key_point_coverage": mean([r["coverage"] for r in in_scope]),
        "faithfulness": mean([float(r["faithful"]) for r in in_scope]),
        "false_refusal_rate": mean([float(r["refused"]) for r in in_scope]),
        "oos_refusal_accuracy": mean([float(oos_handled(r)) for r in oos]),
        "oos_faithfulness": mean([float(r["faithful"]) for r in oos]),
        "by_category": {cat: {"n": len(items), "coverage": mean([r["coverage"] for r in items]),
                              "faithfulness": mean([float(r["faithful"]) for r in items])}
                        for cat, items in sorted(by_category.items())},
    }

    reports = EVAL_DIR / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"{summary['name']}.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports / f"{summary['name']}.md").write_text(render(summary, results), encoding="utf-8")
    print(f"[{summary['name']}] n={summary['n']} failed={summary['failed']} 覆盖率={summary['key_point_coverage']:.3f} "
          f"忠实度={summary['faithfulness']:.3f} 误拒率={summary['false_refusal_rate']:.3f} "
          f"库外处理准确率={summary['oos_refusal_accuracy']:.3f}")
    if summary["failed"] > MAX_FAILED_RATIO * summary["n"]:
        print(f"无效：失败 {summary['failed']}/{summary['n']} 超过 {MAX_FAILED_RATIO:.0%}，多为网络或接口问题，请排查后重跑",
              file=sys.stderr)
        return 1
    return 0


def render(summary: dict, results: list[dict]) -> str:
    lines = [
        f"# 生成质量评测：{summary['name']}",
        "",
        f"- 生成模型：`{summary['chat_model']}`；裁判模型：`{summary['judge_model']}`；mode：`{summary['mode']}`；split：`{summary['split']}`",
        f"- 样本：{summary['n']}（失败 {summary['failed']}）"
        + ("  **⚠️ 失败率超过阈值，本报告无效**" if summary["failed"] > MAX_FAILED_RATIO * summary["n"] else ""),
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 关键点覆盖率（库内） | {summary['key_point_coverage']:.3f} |",
        f"| 忠实度（库内） | {summary['faithfulness']:.3f} |",
        f"| 误拒率（库内） | {summary['false_refusal_rate']:.3f} |",
        f"| 库外处理准确率 | {summary['oos_refusal_accuracy']:.3f} |",
        f"| 忠实度（库外） | {summary['oos_faithfulness']:.3f} |",
        "",
        "## 分题型",
        "",
        "| 题型 | n | 覆盖率 | 忠实度 |",
        "|---|---|---|---|",
    ]
    for cat, m in summary["by_category"].items():
        lines.append(f"| {cat} | {m['n']} | {m['coverage']:.3f} | {m['faithfulness']:.3f} |")
    lines += ["", "## 问题样本（覆盖率 < 0.5、不忠实、误拒或库外未拒答）", "", "| ID | 问题 | 覆盖率 | 忠实 | 拒答 | 说明 |", "|---|---|---|---|---|---|"]
    for r in results:
        if "failed" in r:
            lines.append(f"| {r['id']} | {r['question']} | - | - | - | 失败：{r['failed'][:60]} |")
            continue
        bad = (not r["should_refuse"] and (r["coverage"] < 0.5 or not r["faithful"] or r["refused"])) or \
              (r["should_refuse"] and not oos_handled(r))
        if bad:
            lines.append(f"| {r['id']} | {r['question']} | {r['coverage']:.2f} | {r['faithful']} | {r['refused']} | {r['reason']} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
