from __future__ import annotations

import os

from openai import OpenAI

REWRITE_PROMPT = """你是保险检索查询改写器。把用户的最新问题改写成一条适合在保险条款和产品资料中检索的独立查询。
要求：
1. 结合对话历史补全指代和省略（如"它""这个险"指哪个产品）。
2. 把口语表达换成条款常用说法，如"喝酒开车"→"酒后驾车"、"心脏病突然去世"→"猝死"、"押金"→"住院费用垫付"。
3. 保留产品名称和关键数字，不要回答问题，不要解释。
只输出改写后的查询，不超过 40 个字。"""


class QueryRewriter:
    """用 Qwen 把多轮追问/口语提问改写成独立的检索查询；失败时返回 None，由调用方使用原问题。"""

    def __init__(self):
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.model = os.getenv("REWRITE_MODEL", os.getenv("QWEN_CHAT_MODEL", "qwen3.6-flash"))
        self.client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            timeout=10,
            max_retries=0,
        ) if api_key else None
        self.status = "ready" if self.client else "DASHSCOPE_API_KEY is missing"

    def rewrite(self, question: str, history: list[dict] | None = None) -> str | None:
        if not self.client:
            return None
        turns = "\n".join(
            f"{'用户' if turn['role'] == 'user' else '助手'}：{turn['content'][:300]}"
            for turn in (history or [])[-4:]
        )
        user_content = f"对话历史：\n{turns}\n\n最新问题：{question}" if turns else f"最新问题：{question}"
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REWRITE_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=80,
                extra_body={"enable_thinking": False},
            )
        except Exception as exc:
            self.status = f"rewrite failed: {type(exc).__name__}"
            return None
        text = (response.choices[0].message.content or "").strip().strip("\"'“”")
        self.status = "ready"
        return text[:80] or None
