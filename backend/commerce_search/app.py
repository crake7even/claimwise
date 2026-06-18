from __future__ import annotations

import json

from .search_service import CommerceSearchService


EXAMPLE_QUERIES = [
    "budget samsung phone",
    "iPhone 15 clear case",
    "wireless headphones for music",
    "cheap laptop for school",
    "women summer sun protection jacket",
    "oil control sunscreen spf50",
    "small air fryer for dorm",
]


def build_markdown(output: dict) -> str:
    intent = output["intent"]
    qwen = output.get("qwen_enhancement", {})
    lines = [
        f"## Query: `{output['query']}`",
        "",
        f"- Intent: `{intent['intent']}`",
        f"- Reason: {intent['reason']}",
        f"- Tokens: {', '.join(intent['tokens']) or '-'}",
        f"- Expansion: {', '.join(intent['expanded_terms']) or '-'}",
        f"- Qwen enhancement: {'enabled' if qwen.get('enabled') else qwen.get('reason', 'disabled')}",
        "",
        "| Rank | Product | Brand | Category | Price | Score | Why |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for rank, item in enumerate(output["results"], start=1):
        category = " > ".join(item["categories"][:2])
        lines.append(
            f"| {rank} | {item['name']} | {item['brand']} | {category} | "
            f"{item['price']:.2f} | {item['final_score']:.2f} | {item['rerank_reason']} |"
        )
    return "\n".join(lines)


def run_cli() -> None:
    service = CommerceSearchService()
    print("Shopee Search Strategy Demo")
    print("Type a query, or press Enter to use examples. Type 'exit' to quit.")
    while True:
        query = input("query> ").strip()
        if query.lower() in {"exit", "quit"}:
            return
        if not query:
            for example in EXAMPLE_QUERIES[:3]:
                print(build_markdown(service.search(example, top_k=5)))
                print()
            continue
        print(build_markdown(service.search(query, top_k=8)))


def run_gradio() -> None:
    try:
        import gradio as gr
    except ModuleNotFoundError as exc:
        raise SystemExit("gradio is not installed. Use CLI mode or install project dependencies.") from exc

    service = CommerceSearchService()

    def predict(query: str, top_k: int, mode: str, use_qwen: bool) -> str:
        if not query.strip():
            query = EXAMPLE_QUERIES[0]
        return build_markdown(service.search(query, top_k=int(top_k), mode=mode, use_qwen=use_qwen))

    with gr.Blocks(title="Shopee Search Strategy Demo") as demo:
        gr.Markdown("# Shopee Search Strategy Demo")
        gr.Markdown("Local ecommerce search demo: query intent -> recall -> hybrid rerank -> explanation.")
        with gr.Row():
            query = gr.Textbox(label="Query", value=EXAMPLE_QUERIES[0])
            top_k = gr.Slider(3, 15, value=8, step=1, label="Top K")
            mode = gr.Dropdown(["keyword", "semantic", "hybrid_rerank"], value="hybrid_rerank", label="Mode")
            use_qwen = gr.Checkbox(label="Use Qwen enhancement", value=False)
        run = gr.Button("Search")
        output = gr.Markdown()
        gr.Examples(EXAMPLE_QUERIES, inputs=query)
        run.click(predict, inputs=[query, top_k, mode, use_qwen], outputs=output)
        query.submit(predict, inputs=[query, top_k, mode, use_qwen], outputs=output)
        demo.load(predict, inputs=[query, top_k, mode, use_qwen], outputs=output)
    demo.launch()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()
    if args.gui:
        run_gradio()
    else:
        run_cli()
