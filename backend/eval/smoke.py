"""冒烟场景：用真实模型跑固定对话，按结构断言检查行为（引用、拒答、多轮改写、联网采用等）。

单元测试会 mock 模型，测不到提示词层面的问题；这里补上。每修一个生成相关的 bug，就在 SCENARIOS 里加一个能复现它的场景。

用法：
  python eval/smoke.py                                   # 本地调用 api_server
  python eval/smoke.py --base-url https://xxx.onrender.com   # 线上 API
  python eval/smoke.py --only web_offline_topic          # 只跑指定场景
需要 DASHSCOPE_API_KEY；联网场景需要 BOCHA_API_KEY。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

NO_CONTEXT_MARK = "知识库中没有找到"


class Reply:
    def __init__(self, text: str, sources: list[dict], rewritten: str | None, errors: list[str], seconds: float):
        self.text = text
        self.sources = sources
        self.rewritten = rewritten
        self.errors = errors
        self.seconds = seconds

    @property
    def cited(self) -> set[int]:
        return {int(n) for n in re.findall(r"\[(\d{1,2})\]", self.text)}

    def ids(self, kind: str) -> set[int]:
        return {s["id"] for s in self.sources if s["kind"] == kind}


Check = Callable[[Reply], Optional[str]]  # 返回 None 表示通过，否则返回失败原因


def cites_any(r: Reply) -> str | None:
    return None if r.cited & {s["id"] for s in r.sources} else "回答没有引用任何来源编号"


def cites_web(r: Reply) -> str | None:
    if not r.ids("web"):
        return "没有返回联网来源"
    return None if r.cited & r.ids("web") else f"回答未引用联网来源（联网编号 {sorted(r.ids('web'))}，实际引用 {sorted(r.cited)}）"


def contains(*words: str) -> Check:
    return lambda r: None if all(w in r.text for w in words) else f"回答缺少：{[w for w in words if w not in r.text]}"


def contains_any(*words: str) -> Check:
    return lambda r: None if any(w in r.text for w in words) else f"回答不包含以下任一：{list(words)}"


def not_contains(*words: str) -> Check:
    return lambda r: None if not any(w in r.text for w in words) else f"回答出现了不应出现的：{[w for w in words if w in r.text]}"


def conclusion_not(*words: str) -> Check:
    """回答不能以这些说法开头（如"资料中未提及"）；首句中的限定说明（如"未提及2025年的案例"）不受限制。"""
    def check(r: Reply) -> Optional[str]:
        head = re.split(r"[。\n]", r.text.strip(), maxsplit=1)[0].lstrip("*#>：: ")
        head = re.sub(r"^(结论|回答)[:：]", "", head).lstrip("*#>：: ")
        return None if not head.startswith(words) else f"结论是：{head[:60]}"
    return check


def rewritten_contains(*words: str) -> Check:
    return lambda r: None if r.rewritten and all(w in r.rewritten for w in words) else f"改写查询不符合预期：{r.rewritten!r}"


def refused_without_sources(r: Reply) -> str | None:
    return None if not r.sources and NO_CONTEXT_MARK in r.text else "库外问题没有直接拒答"


def no_errors(r: Reply) -> str | None:
    return None if not r.errors else f"出现 error 事件：{r.errors}"


# 每个场景是若干轮对话；只对最后一轮做断言，前面的轮次用于构造真实历史。
SCENARIOS: list[dict] = [
    {
        "name": "exclusion_with_citation",
        "turns": [("员工喝了酒自己开车出事，意外险赔吗？", "semantic")],
        "checks": [no_errors, cites_any, contains_any("不赔", "不承担")],
    },
    {
        "name": "numeric_requirements",
        "turns": [("施工保对投保工程有什么要求？", "semantic")],
        "checks": [no_errors, cites_any, contains("50万", "1亿", "三级")],
    },
    {
        "name": "value_not_in_docs",
        "turns": [("施工保的第三者责任保额是多少？", "semantic")],
        "checks": [no_errors, contains("为准")],
    },
    {
        "name": "out_of_scope_refusal",
        "turns": [("今天北京天气怎么样？", "quick")],
        "checks": [no_errors, refused_without_sources],
    },
    {
        "name": "multi_turn_rewrite",
        "turns": [("员工喝了酒自己开车出事，意外险赔吗？", "semantic"), ("那猝死呢？", "quick")],
        "checks": [no_errors, rewritten_contains("猝死"), cites_any],
    },
    {
        # 回归：联网模式下本地无答案时，模型应采用联网资料，而不是回答"资料中未提及"
        "name": "web_offline_topic",
        "turns": [("介绍下雇主责任险", "quick"), ("有什么最新关于无接触交通事故的理赔案例吗", "web")],
        "checks": [no_errors, cites_web, conclusion_not("资料中未提及", "未提及", "没有找到")],
    },
    {
        "name": "web_news",
        "turns": [("保险行业 AI 最新新闻", "web")],
        "checks": [no_errors, cites_web],
    },
    {
        # 回归：用户追问"上网搜索"时应基于上一问联网检索并采用结果
        "name": "web_followup_command",
        "turns": [("有什么最新关于无接触交通事故的理赔案例吗", "quick"), ("上网搜索一下", "web")],
        "checks": [no_errors, cites_web, rewritten_contains("无接触")],
    },
]


def ask_local(message: str, mode: str, history: list[dict]) -> Reply:
    import api_server

    started = time.perf_counter()
    lines = "".join(api_server.stream_answer(message, mode, history)).splitlines()
    return parse_events(lines, started)


def ask_remote(base_url: str, message: str, mode: str, history: list[dict]) -> Reply:
    started = time.perf_counter()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps({"message": message, "mode": mode, "history": history}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        lines = [line.decode("utf-8") for line in response]
    return parse_events(lines, started)


def parse_events(lines: list[str], started: float) -> Reply:
    text, sources, rewritten, errors = "", [], None, []
    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        if event["type"] == "sources":
            sources, rewritten = event["sources"], event.get("rewritten")
        elif event["type"] == "delta":
            text += event["text"]
        elif event["type"] == "error":
            errors.append(event["message"])
    return Reply(text, sources, rewritten, errors, time.perf_counter() - started)


def run_scenario(scenario: dict, ask: Callable[[str, str, list[dict]], Reply]) -> dict:
    history: list[dict] = []
    reply = None
    try:
        for message, mode in scenario["turns"]:
            reply = ask(message, mode, history)
            history += [{"role": "user", "content": message}, {"role": "assistant", "content": reply.text}]
    except Exception as exc:
        return {"name": scenario["name"], "passed": False, "failures": [f"请求失败：{type(exc).__name__}: {exc}"]}
    failures = [reason for check in scenario["checks"] if (reason := check(reply))]
    return {
        "name": scenario["name"],
        "passed": not failures,
        "failures": failures,
        "seconds": round(reply.seconds, 1),
        "rewritten": reply.rewritten,
        "answer": reply.text[:160].replace("\n", " "),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ClaimWise 冒烟场景")
    parser.add_argument("--base-url", help="线上 API 地址；不填则在本地直接调用 api_server")
    parser.add_argument("--only", help="逗号分隔的场景名")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.only:
        wanted = set(args.only.split(","))
        scenarios = [s for s in SCENARIOS if s["name"] in wanted]
    if args.base_url:
        ask = lambda m, mode, h: ask_remote(args.base_url, m, mode, h)  # noqa: E731
    else:
        import api_server  # 预先导入，避免并发初始化
        if api_server.qwen_client() is None:
            print("需要 DASHSCOPE_API_KEY", file=sys.stderr)
            return 1
        ask = ask_local

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda s: run_scenario(s, ask), scenarios))

    for result in results:
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"[{mark}] {result['name']} ({result.get('seconds', '-')}s) 改写={result.get('rewritten')!r}")
        for failure in result["failures"]:
            print(f"       - {failure}")
        if not result["passed"] and result.get("answer"):
            print(f"       回答：{result['answer']}")
    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
