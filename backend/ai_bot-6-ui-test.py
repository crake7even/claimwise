from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterator

import gradio as gr
from openai import OpenAI

from rag_upgrade import HybridRagService
from rag_upgrade.config import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
UI_ASSETS_DIR = PROJECT_ROOT / "ui_assets"
LOGO_PATH = PROJECT_ROOT / "logo.png"

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
            f"[本地资料{index}] 来源: {item['file_name']} chunk={item['chunk_id']} "
            f"retrievers={retrievers}\n{item['content'][:1200]}"
        )
    for index, item in enumerate(result["external"], start=1):
        lines.append(
            f"[联网资料{index}] 标题: {item['title']}\nURL: {item['url']}\n{item['content'][:800]}"
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
        lines.extend(["", "联网搜索："])
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


def stream_answer(
    service: HybridRagService,
    query: str,
    use_es: bool,
    use_embedding: bool,
    use_external: bool,
) -> Iterator[str]:
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
    UI_ASSETS_DIR.mkdir(exist_ok=True)
    service = HybridRagService()

    def mode_to_flags(search_mode: str) -> tuple[bool, bool, bool]:
        if search_mode == "语义理解":
            return True, True, False
        if search_mode == "联网搜索":
            return True, False, True
        return True, False, False

    def chat(query: str, history: list[dict], search_mode: str):
        query = (query or "").strip()
        history = list(history or [])
        if not query:
            yield "", history
            return

        fast_search, semantic_search, web_search = mode_to_flags(search_mode)
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": f"正在使用「{search_mode}」查找资料，请稍候..."})
        yield "", history

        for partial in stream_answer(
            service,
            query,
            use_es=fast_search,
            use_embedding=semantic_search,
            use_external=web_search,
        ):
            history[-1]["content"] = partial
            yield "", history

    def clear():
        return "", []

    css = """
    :root {
        --ink: #172033;
        --muted: #667085;
        --line: #d7dde8;
        --paper: #fbfcff;
        --panel: #ffffff;
        --blue: #2457d6;
        --blue-2: #edf3ff;
        --green: #16845b;
        --amber: #a15c00;
    }
    html, body {
        overflow: hidden;
    }
    .gradio-container {
        max-width: 1360px !important;
        min-height: 100vh !important;
        height: 100vh !important;
        margin: 0 auto !important;
        padding: 10px 18px 14px !important;
        color: var(--ink);
        background:
            radial-gradient(circle at top left, rgba(36, 87, 214, .13), transparent 340px),
            linear-gradient(180deg, rgba(238,244,255,.86), rgba(255,255,255,0) 220px),
            var(--paper);
        font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    }
    #hero {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: linear-gradient(135deg, #ffffff 0%, #eef4ff 56%, #e9f7f0 100%);
        padding: 12px 16px;
        margin: 0 0 10px;
        box-shadow: 0 14px 36px rgba(23, 32, 51, .08);
    }
    .hero-inner {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .hero-logo {
        width: 42px;
        height: 42px;
        border-radius: 8px;
        object-fit: contain;
        background: white;
        border: 1px solid var(--line);
        padding: 6px;
    }
    .hero-title {
        font-size: 20px;
        line-height: 1.2;
        font-weight: 700;
        margin: 0 0 2px;
        letter-spacing: 0;
    }
    .hero-subtitle {
        color: var(--muted);
        font-size: 12px;
        line-height: 1.5;
        margin: 0;
    }
    #workspace {
        gap: 14px;
        align-items: stretch;
        height: calc(100vh - 94px);
    }
    #chat-panel, #examples-panel {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
        box-shadow: 0 10px 24px rgba(23, 32, 51, .06);
        padding: 12px;
    }
    #chat-panel {
        min-height: 0;
        display: flex;
        flex-direction: column;
    }
    #examples-panel {
        height: calc(100vh - 94px);
        position: sticky;
        top: 10px;
        overflow: hidden;
    }
    .panel-title {
        font-weight: 700;
        font-size: 15px;
        margin: 2px 0 8px;
        color: var(--ink);
    }
    .quick-tip {
        padding: 9px 10px;
        border-radius: 8px;
        background: #f7fafc;
        border: 1px solid var(--line);
        color: var(--muted);
        font-size: 12px;
        line-height: 1.6;
        margin: 8px 0 12px;
    }
    .example-button {
        width: 100%;
        margin-bottom: 8px;
        border-radius: 8px !important;
        border-color: var(--line) !important;
        text-align: left !important;
        min-height: 38px !important;
    }
    .example-button:hover {
        background: var(--blue-2) !important;
        border-color: #b9c9ff !important;
    }
    .mode-pill {
        display: inline-flex;
        align-items: center;
        padding: 6px 10px;
        border-radius: 999px;
        background: var(--blue-2);
        color: var(--blue);
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .assistant-card {
        padding: 12px;
        border-radius: 8px;
        background: linear-gradient(180deg, #ffffff, #f7faff);
        border: 1px solid var(--line);
        margin-bottom: 12px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.65;
    }
    #input-row {
        gap: 8px;
        align-items: center;
        margin-top: 8px;
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 8px;
        background: white;
        box-shadow: 0 8px 18px rgba(23, 32, 51, .06);
    }
    #send-button {
        min-width: 78px;
        border-radius: 999px !important;
    }
    #clear-button {
        margin-top: 8px;
    }
    #mode-select {
        max-width: 138px;
    }
    #mode-select label {
        display: none !important;
    }
    #mode-select .wrap,
    #mode-select input,
    #mode-select select {
        border-radius: 999px !important;
    }
    #chat-panel .wrap.svelte-6roggh {
        border: none !important;
    }
    @media (max-width: 900px) {
        html, body { overflow: auto; }
        .gradio-container { height: auto !important; min-height: 100vh !important; }
        #workspace { height: auto; }
        .hero-inner { align-items: flex-start; }
        .hero-title { font-size: 18px; }
        #examples-panel { height: auto; position: static; }
    }
    """

    logo_html = ""
    if LOGO_PATH.exists():
        logo_html = f"<img class='hero-logo' src='/file={LOGO_PATH.as_posix()}' alt='logo'>"
    else:
        logo_html = "<div class='hero-logo'></div>"

    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
        font=["Microsoft YaHei", "Segoe UI", "sans-serif"],
    )

    with gr.Blocks(title="保险资料智能问答系统", css=css, theme=theme) as demo:
        gr.HTML(
            f"""
            <section id="hero">
                <div class="hero-inner">
                    {logo_html}
                    <div>
                        <h1 class="hero-title">保险资料智能问答系统</h1>
                        <p class="hero-subtitle">
                            面向业务人员的本地资料问答工具。默认优先查询已审核的保险资料，
                            可按需开启语义理解和联网搜索。
                        </p>
                    </div>
                </div>
            </section>
            """
        )

        with gr.Row(elem_id="workspace"):
            with gr.Column(scale=8, min_width=640, elem_id="chat-panel"):
                chatbot = gr.Chatbot(
                    label="AI 助手",
                    type="messages",
                    height=430,
                    show_copy_button=True,
                    placeholder=(
                        "我是你的保险资料 AI 助手。"
                        "可以直接询问产品介绍、保障范围、适用场景和理赔流程。"
                    ),
                )
                with gr.Row(elem_id="input-row"):
                    search_mode = gr.Dropdown(
                        choices=["快速检索", "语义理解", "联网搜索"],
                        value="快速检索",
                        show_label=False,
                        container=False,
                        elem_id="mode-select",
                    )
                    query = gr.Textbox(
                        show_label=False,
                        placeholder="请输入问题，例如：介绍下雇主责任险",
                        lines=1,
                        max_lines=4,
                        scale=8,
                        container=False,
                    )
                    submit = gr.Button("发送", variant="primary", scale=1, elem_id="send-button")
                clear_btn = gr.Button("清空对话", variant="secondary", elem_id="clear-button")

            with gr.Column(scale=3, min_width=280, elem_id="examples-panel"):
                gr.HTML("<div class='mode-pill'>默认：快速检索</div>")
                gr.HTML("<div class='panel-title'>常问问题</div>")
                gr.HTML(
                    "<div class='assistant-card'>"
                    "右侧问题固定展示，点击后会填入输入框。"
                    "如需查询新闻或网页信息，可在输入框左侧切换为“联网搜索”。"
                    "</div>"
                )
                for example in EXAMPLES:
                    gr.Button(example, elem_classes=["example-button"]).click(
                        lambda value=example: value,
                        outputs=query,
                    )

        submit.click(
            chat,
            inputs=[query, chatbot, search_mode],
            outputs=[query, chatbot],
        )
        query.submit(
            chat,
            inputs=[query, chatbot, search_mode],
            outputs=[query, chatbot],
        )
        clear_btn.click(clear, outputs=[query, chatbot])

    port = int(os.getenv("RAG_WEBUI_PORT", "7864"))
    allowed_paths = [str(UI_ASSETS_DIR)]
    if LOGO_PATH.exists():
        allowed_paths.append(str(LOGO_PATH))
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        inbrowser=inbrowser,
        show_error=True,
        allowed_paths=allowed_paths,
    )


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
