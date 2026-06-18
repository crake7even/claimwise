from __future__ import annotations

import argparse
import os
from typing import Iterator

import gradio as gr
from openai import OpenAI

from rag_upgrade import HybridRagService
from rag_upgrade.config import load_dotenv


SYSTEM_PROMPT = """你是一个保险资料检索问答助手。
必须优先依据给定的本地知识库片段回答；如果本地资料不足，可以参考外部搜索结果，并明确说明依据来源。
不要编造保险条款。回答使用中文，先给结论，再列要点。"""


EXAMPLES = [
    "介绍下雇主责任险",
    "雇主责任险和工伤保险有什么主要区别？",
    "施工保主要适用于哪些场景？",
    "财产一切险的理赔流程是什么？",
    "搜索AI新闻",
]


def ensure_localhost_no_proxy() -> None:
    local_hosts = ["localhost", "127.0.0.1", "::1"]
    for env_name in ("NO_PROXY", "no_proxy"):
        values = [item.strip() for item in os.environ.get(env_name, "").split(",") if item.strip()]
        for host in local_hosts:
            if host not in values:
                values.append(host)
        os.environ[env_name] = ",".join(values)


def build_context_block(result: dict) -> str:
    lines: list[str] = []
    for index, item in enumerate(result["contexts"], start=1):
        retrievers = ", ".join(sorted(set(item.get("retrievers", []))))
        lines.append(
            f"[本地片段{index}] 来源: {item['file_name']} chunk={item['chunk_id']} "
            f"retrievers={retrievers}\n{item['content'][:1200]}"
        )
    for index, item in enumerate(result["external"], start=1):
        lines.append(
            f"[外部搜索{index}] 标题: {item['title']}\nURL: {item['url']}\n{item['content'][:800]}"
        )
    return "\n\n".join(lines)


def build_fallback_answer(result: dict) -> str:
    lines = [
        "当前未配置 `DASHSCOPE_API_KEY`，已返回检索结果摘要，暂不调用 Qwen 生成最终答案。",
        "",
        "检索状态：",
    ]
    for key, value in result["status"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "召回片段："])
    for index, item in enumerate(result["contexts"], start=1):
        retrievers = ", ".join(sorted(set(item.get("retrievers", []))))
        preview = item["content"].replace("\n", " ")[:240]
        lines.append(f"{index}. {item['file_name']} chunk={item['chunk_id']} [{retrievers}]：{preview}")
    if result["external"]:
        lines.extend(["", "外部搜索："])
        for index, item in enumerate(result["external"], start=1):
            lines.append(f"{index}. {item['title']} - {item['url']}")
    return "\n".join(lines)


def qwen_client() -> OpenAI | None:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    )


def stream_answer(service: HybridRagService, query: str, use_es: bool, use_embedding: bool, use_external: bool) -> Iterator[str]:
    result = service.search(
        query=query,
        top_k=int(os.getenv("RAG_TOP_K", "6")),
        use_es=use_es,
        use_embedding=use_embedding,
        use_external=use_external,
    )
    client = qwen_client()
    if client is None:
        yield build_fallback_answer(result)
        return

    context_block = build_context_block(result)
    user_prompt = f"""用户问题：
{query}

可用资料：
{context_block if context_block else "没有检索到可用资料。"}

请基于以上资料回答。"""
    model = os.getenv("QWEN_CHAT_MODEL", os.getenv("QWEN_MODEL", "qwen-turbo"))
    content = ""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if not delta:
                continue
            content += delta
            yield content
    except Exception as exc:
        yield build_fallback_answer(result) + f"\n\nQwen 调用失败：{type(exc).__name__}: {exc}"


def run_cli(query: str, use_es: bool, use_embedding: bool, use_external: bool) -> None:
    service = HybridRagService()
    final = ""
    for partial in stream_answer(service, query, use_es, use_embedding, use_external):
        final = partial
    print(final)


def run_gui(inbrowser: bool = True) -> None:
    service = HybridRagService()

    def chat(query: str, history: list[dict], use_es: bool, use_embedding: bool, use_external: bool):
        query = (query or "").strip()
        history = list(history or [])
        if not query:
            yield "", history
            return
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": ""})
        yield "", history
        for partial in stream_answer(service, query, use_es, use_embedding, use_external):
            history[-1]["content"] = partial
            yield "", history

    def clear():
        return "", []

    def status_text() -> str:
        status = service.status()
        return "\n".join(f"- `{key}`: {value}" for key, value in status.items())

    css = """
    .gradio-container { max-width: 1280px !important; margin: 0 auto !important; }
    #main { gap: 16px; }
    #side { border-left: 1px solid #e5e7eb; padding-left: 16px; }
    """
    with gr.Blocks(title="AI搜索问答升级版", css=css) as demo:
        gr.Markdown("# AI搜索问答升级版")
        gr.Markdown("本地文档 RAG + Elasticsearch BM25 + Qwen embedding 向量召回 + Tavily 外部搜索源。")
        with gr.Row(elem_id="main"):
            with gr.Column(scale=7):
                chatbot = gr.Chatbot(type="messages", height=560, show_copy_button=True)
                with gr.Row():
                    query = gr.Textbox(show_label=False, placeholder="请输入问题", lines=1, scale=8)
                    submit = gr.Button("发送", variant="primary", scale=1)
                clear_btn = gr.Button("清空对话")
            with gr.Column(scale=3, elem_id="side"):
                gr.Markdown("### 检索开关")
                use_es = gr.Checkbox(label="使用 Elasticsearch", value=True)
                use_embedding = gr.Checkbox(label="使用 Qwen embedding", value=True)
                use_external = gr.Checkbox(label="使用外部搜索源", value=True)
                gr.Markdown("### 当前状态")
                status = gr.Markdown(status_text())
                refresh = gr.Button("刷新状态")
                gr.Markdown("### 示例问题")
                for example in EXAMPLES:
                    gr.Button(example).click(lambda value=example: value, outputs=query)

        submit.click(chat, inputs=[query, chatbot, use_es, use_embedding, use_external], outputs=[query, chatbot])
        query.submit(chat, inputs=[query, chatbot, use_es, use_embedding, use_external], outputs=[query, chatbot])
        clear_btn.click(clear, outputs=[query, chatbot])
        refresh.click(status_text, outputs=status)

    port = int(os.getenv("RAG_WEBUI_PORT", "7862"))
    demo.launch(server_name="127.0.0.1", server_port=port, inbrowser=inbrowser, show_error=True)


def main() -> None:
    load_dotenv()
    ensure_localhost_no_proxy()
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--no-es", action="store_true")
    parser.add_argument("--no-embedding", action="store_true")
    parser.add_argument("--no-external", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.cli or args.query:
        run_cli(
            query=args.query or EXAMPLES[0],
            use_es=not args.no_es,
            use_embedding=not args.no_embedding,
            use_external=not args.no_external,
        )
        return
    run_gui(inbrowser=not args.no_browser)


if __name__ == "__main__":
    main()
