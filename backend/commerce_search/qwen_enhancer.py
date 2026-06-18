from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .config import load_dotenv


SYSTEM_PROMPT = """You are an ecommerce search query understanding assistant.
Return strict JSON with fields: rewritten_query, intent, key_terms, filters, reason.
Do not include markdown."""


def enhance_query_with_qwen(query: str) -> dict:
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return {
            "enabled": False,
            "reason": "DASHSCOPE_API_KEY is not configured; local rule-based intent is used.",
        }

    user_prompt = (
        "Analyze this ecommerce search query for Shopee-style product search. "
        f"Query: {query}"
    )
    payload = {
        "model": os.getenv("QWEN_MODEL", "qwen-plus"),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 256,
    }
    request = urllib.request.Request(
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {
            "enabled": False,
            "reason": f"DashScope HTTP {exc.code}: {error_body[:200]}",
        }
    except Exception as exc:
        return {
            "enabled": False,
            "reason": f"DashScope request failed: {type(exc).__name__}: {exc}",
        }

    content = body["choices"][0]["message"].get("content") or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"raw": content}
    parsed["enabled"] = True
    parsed["model"] = body.get("model", payload["model"])
    return parsed


if __name__ == "__main__":
    import argparse
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()
    print(json.dumps(enhance_query_with_qwen(args.query), ensure_ascii=False, indent=2))
