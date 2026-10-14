from __future__ import annotations

import os
from typing import Iterator, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, Field

from rag_upgrade import HybridRagService
from rag_upgrade.config import load_dotenv


SYSTEM_PROMPT = """你是一个保险资料检索问答助手。
必须优先依据给定的本地知识库片段回答；如果本地资料不足，可以参考外部搜索结果，并明确说明依据来源。
不要编造保险条款。回答使用中文，先给结论，再列要点。"""

MODE_FLAGS = {
    "quick": (True, False, False),
    "semantic": (True, True, False),
    "web": (True, False, True),
}


class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)
    mode: Literal["quick", "semantic", "web"] = "quick"


load_dotenv()


def allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["http://127.0.0.1:3000", "http://localhost:3000"]


app = FastAPI(
    title="Insurance RAG API",
    version="1.0.0",
    description="Hybrid retrieval API for the Insurance RAG Assistant.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
service = HybridRagService()


def qwen_client() -> OpenAI | None:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )


def build_context_block(result: dict) -> str:
    lines: list[str] = []
    for index, item in enumerate(result["contexts"], start=1):
        retrievers = ", ".join(sorted(set(item.get("retrievers", []))))
        lines.append(
            f"[本地资料{index}] 来源: {item['file_name']} chunk={item['chunk_id']} "
            f"retrievers={retrievers}\n{item['content'][:1200]}"
        )
    for index, item in enumerate(result["external"], start=1):
        lines.append(
            f"[联网资料{index}] 标题: {item['title']}\nURL: {item['url']}\n{item['content'][:800]}"
        )
    return "\n\n".join(lines)


def fallback_answer(result: dict) -> str:
    lines = [
        "当前未配置 DASHSCOPE_API_KEY，已返回检索摘要，暂不调用 Qwen 生成最终答案。",
        "",
        "召回片段：",
    ]
    for index, item in enumerate(result["contexts"], start=1):
        retrievers = ", ".join(sorted(set(item.get("retrievers", []))))
        preview = item["content"].replace("\n", " ")[:260]
        lines.append(f"{index}. {item['file_name']} [{retrievers}]：{preview}")
    if result["external"]:
        lines.extend(["", "联网搜索："])
        for index, item in enumerate(result["external"], start=1):
            lines.append(f"{index}. {item['title']} - {item['url']}")
    return "\n".join(lines)


def stream_answer(message: str, mode: str) -> Iterator[str]:
    use_es, use_embedding, use_external = MODE_FLAGS.get(mode, MODE_FLAGS["quick"])
    result = service.search(
        query=message,
        top_k=int(os.getenv("RAG_TOP_K", "6")),
        use_es=use_es,
        use_embedding=use_embedding,
        use_external=use_external,
    )

    client = qwen_client()
    if client is None:
        yield fallback_answer(result)
        return

    context_block = build_context_block(result)
    user_prompt = f"""用户问题：
{message}

可用资料：
{context_block if context_block else "没有检索到可用资料。"}

请基于以上资料回答。"""
    response = client.chat.completions.create(
        model=os.getenv("QWEN_CHAT_MODEL", os.getenv("QWEN_MODEL", "qwen3.6-flash")),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        stream=True,
        extra_body={"enable_thinking": False},
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta


@app.get("/api/health")
def health() -> dict:
    chunks = len(service.chunks)
    return {
        "ok": chunks > 0,
        "chunks": chunks,
        "quick": chunks > 0,
        "semantic": bool(service.embedding and service.embedding.enabled),
        "web": bool(service.external.api_key),
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    message = request.message.strip()
    if not message:
        return StreamingResponse(iter(["请输入问题。"]), media_type="text/plain; charset=utf-8")
    return StreamingResponse(stream_answer(message, request.mode), media_type="text/plain; charset=utf-8")
