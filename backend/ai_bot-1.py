import pprint
import urllib.parse
import json5
import gradio as gr
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
import os
from qwen_agent.gui import WebUI


def load_local_env():
    """Load key-value pairs from the local .env file without printing secrets."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def ensure_localhost_no_proxy():
    """Keep Gradio's localhost startup checks away from system proxies."""
    local_hosts = ['localhost', '127.0.0.1', '::1']
    for env_name in ('NO_PROXY', 'no_proxy'):
        values = [item.strip() for item in os.environ.get(env_name, '').split(',') if item.strip()]
        for host in local_hosts:
            if host not in values:
                values.append(host)
        os.environ[env_name] = ','.join(values)


# 步骤 1（可选）：添加一个名为 `my_image_gen` 的自定义工具。
@register_tool('my_image_gen')
class MyImageGen(BaseTool):
    # `description` 用于告诉智能体该工具的功能。
    description = 'AI 绘画（图像生成）服务，输入文本描述，返回基于文本信息绘制的图像 URL。'
    # `parameters` 告诉智能体该工具有哪些输入参数。
    parameters = [{
        'name': 'prompt',
        'type': 'string',
        'description': '期望的图像内容的详细描述',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        # `params` 是由 LLM 智能体生成的参数。
        prompt = json5.loads(params)['prompt']
        prompt = urllib.parse.quote(prompt)
        return json5.dumps(
            {'image_url': f'https://image.pollinations.ai/prompt/{prompt}'},
            ensure_ascii=False)


def init_agent_service():
    """初始化助手服务"""
    # 步骤 2：配置您所使用的 LLM。
    # llm_cfg = {
    #     # 使用 DashScope 提供的模型服务：
    #     'model': 'qwen-max',
    #     'model_server': 'dashscope',
    #     'api_key': os.getenv('DASHSCOPE_API_KEY'),  # 从环境变量获取API Key
    #     'generate_cfg': {
    #         'top_p': 0.8
    #     }
    # }

    llm_cfg = {
        # 使用 DashScope 提供的模型服务：
        'model': 'qwen-turbo',
        'model_server': 'dashscope',
        'api_key': os.getenv('DASHSCOPE_API_KEY'),  # 从环境变量获取API Key
        'generate_cfg': {
            'top_p': 0.8,
            'use_raw_api': False,
            'max_tokens': 800
        }
    }

    # 步骤 3：创建一个智能体。这里我们以 `Assistant` 智能体为例，它能够使用工具并读取文件。
    system_instruction = '''你是一个保险问答助手。
请优先根据给定文档回答用户问题；如果文档中没有依据，要明确说明。
回答要使用中文，尽量结构清晰，不要编造保险条款。
面试演示场景下，默认回答要简洁，优先给出结论和要点，除非用户要求详细展开。'''
    tools = []
    # 获取文件夹下所有文件
    file_dir = os.path.join(os.path.dirname(__file__), 'docs')
    files = []
    if os.path.exists(file_dir):
        # 遍历目录下的所有文件
        for file in os.listdir(file_dir):
            file_path = os.path.join(file_dir, file)
            if os.path.isfile(file_path) and file.lower().endswith('.txt'):  # 确保是文件而不是目录
                files.append(file_path)
    print('files=', files)

    bot = Assistant(llm=llm_cfg,
                    system_message=system_instruction,
                    function_list=tools,
                    files=files,
                    rag_cfg={
                        'rag_keygen_strategy': 'none'
                    })
    return bot


def app_tui():
    """终端交互模式
    
    提供命令行交互界面，支持：
    - 连续对话
    - 文件输入
    - 实时响应
    """
    try:
        # 初始化助手
        bot = init_agent_service()

        # 对话历史
        messages = []
        while True:
            try:
                # 获取用户输入
                query = input('user question: ')
                
                # 输入验证
                if not query:
                    print('user question cannot be empty！')
                    continue
                    
                # 构建消息
                messages.append({'role': 'user', 'content': query})

                print("正在处理您的请求...")
                # 运行助手并处理响应
                response = []
                current_index = 0
                first_chunk = True
                for response_chunk in bot.run(messages=messages):
                    if first_chunk:
                        # 尝试获取并打印召回的文档内容
                        if hasattr(bot, 'retriever') and bot.retriever:
                            print("\n===== 召回的文档内容 =====")
                            retrieved_docs = bot.retriever.retrieve(query)
                            if retrieved_docs:
                                for i, doc in enumerate(retrieved_docs):
                                    print(f"\n文档片段 {i+1}:")
                                    print(f"内容: {doc.page_content}")
                                    print(f"元数据: {doc.metadata}")
                            else:
                                print("没有召回任何文档内容")
                            print("===========================\n")
                        first_chunk = False

                    # The response is a list of messages. We are interested in the assistant's message.
                    if response_chunk and response_chunk[0]['role'] == 'assistant':
                        assistant_message = response_chunk[0]
                        new_content = assistant_message.get('content', '')
                        print(new_content[current_index:], end='', flush=True)
                        current_index = len(new_content)
                    
                    response = response_chunk
                
                print() # New line after streaming.

                messages.extend(response)
            except Exception as e:
                print(f"处理请求时出错: {str(e)}")
                print("请重试或输入新的问题")
    except Exception as e:
        print(f"启动终端模式失败: {str(e)}")


def app_gui():
    """图形界面模式，使用 Gradio Blocks 构建演示页面"""
    try:
        print("正在启动 Web 界面...")

        # 后端 RAG 初始化逻辑保持不变
        bot = init_agent_service()

        custom_css = """
        .gradio-container {
            max-width: 1280px !important;
            margin: 0 auto !important;
            padding: 20px 24px 28px 24px !important;
        }

        #app-header {
            padding: 22px 26px;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            margin-bottom: 18px;
        }

        #app-header h1 {
            margin: 0 0 8px 0;
            font-size: 28px;
            line-height: 1.25;
            color: #0f172a;
            font-weight: 700;
        }

        #app-header p {
            margin: 0;
            font-size: 14px;
            line-height: 1.7;
            color: #475569;
        }

        #main-layout {
            gap: 18px;
            align-items: stretch;
        }

        #chat-panel, #side-panel {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            background: #ffffff;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            padding: 16px;
        }

        #side-panel {
            min-height: 640px;
        }

        #input-row {
            gap: 10px;
            align-items: center;
            margin-top: 12px;
        }

        #send-button {
            min-width: 92px;
        }

        .example-button {
            width: 100%;
            margin-bottom: 8px;
        }

        .info-box {
            padding: 12px 14px;
            border-radius: 10px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            color: #334155;
            font-size: 13px;
            line-height: 1.7;
        }

        @media (max-width: 900px) {
            .gradio-container {
                padding: 14px !important;
            }

            #app-header h1 {
                font-size: 22px;
            }

            #side-panel {
                min-height: auto;
            }
        }
        """

        theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            neutral_hue="slate",
            font=["Microsoft YaHei", "Segoe UI", "Arial", "sans-serif"]
        )

        def build_ui_messages(agent_messages):
            ui_messages = []
            for msg in agent_messages or []:
                role = msg.get("role")
                content = msg.get("content", "")
                if not content:
                    continue
                if role in ("user", "assistant"):
                    ui_messages.append({
                        "role": role,
                        "content": content
                    })
            return ui_messages

        def chat_response(user_text, agent_messages):
            user_text = (user_text or "").strip()
            agent_messages = list(agent_messages or [])

            if not user_text:
                yield "", agent_messages, build_ui_messages(agent_messages)
                return

            agent_messages.append({
                "role": "user",
                "content": user_text
            })

            ui_messages = build_ui_messages(agent_messages)
            ui_messages.append({
                "role": "assistant",
                "content": ""
            })

            yield "", agent_messages, ui_messages

            final_response = []
            try:
                for response_chunk in bot.run(messages=agent_messages):
                    final_response = response_chunk

                    assistant_content = ""
                    for msg in reversed(response_chunk or []):
                        if msg.get("role") == "assistant":
                            assistant_content = msg.get("content", "") or ""
                            break

                    if assistant_content:
                        ui_messages[-1]["content"] = assistant_content
                        yield "", agent_messages, ui_messages

                if final_response:
                    agent_messages.extend(final_response)

                yield "", agent_messages, build_ui_messages(agent_messages)

            except Exception as e:
                ui_messages[-1]["content"] = f"请求失败：{str(e)}"
                safe_messages = agent_messages[:-1]
                yield "", safe_messages, ui_messages

        def clear_chat():
            return "", [], []

        with gr.Blocks(
            theme=theme,
            css=custom_css,
            title="商业保险智能问答系统"
        ) as demo:

            gr.HTML(
                """
                <div id="app-header">
                    <h1>商业保险智能问答系统</h1>
                    <p>
                        基于本地保险条款知识库与 Qwen-Agent 的 RAG 检索问答应用。
                        支持围绕雇主责任险、施工保、财产险等资料进行产品解读、保障范围说明和理赔场景问答。
                    </p>
                </div>
                """
            )

            agent_state = gr.State([])

            with gr.Row(elem_id="main-layout"):
                with gr.Column(scale=7, min_width=620, elem_id="chat-panel"):
                    chatbot = gr.Chatbot(
                        label="智能问答",
                        type="messages",
                        height=560,
                        show_copy_button=True,
                        placeholder="请输入一个保险相关问题，系统会优先基于本地知识库回答。"
                    )

                    with gr.Row(elem_id="input-row"):
                        user_input = gr.Textbox(
                            show_label=False,
                            placeholder="例如：雇主责任险主要保障哪些内容？",
                            lines=1,
                            max_lines=4,
                            scale=8,
                            container=False
                        )
                        submit_btn = gr.Button(
                            "发送",
                            variant="primary",
                            scale=1,
                            elem_id="send-button"
                        )

                with gr.Column(scale=3, min_width=300, elem_id="side-panel"):
                    gr.Markdown("### 示例问题")

                    example_1 = gr.Button(
                        "介绍一下雇主责任险",
                        elem_classes=["example-button"]
                    )
                    example_2 = gr.Button(
                        "雇主责任险主要保障哪些内容？",
                        elem_classes=["example-button"]
                    )
                    example_3 = gr.Button(
                        "施工保适合什么业务场景？",
                        elem_classes=["example-button"]
                    )
                    example_4 = gr.Button(
                        "发生工伤事故时理赔流程是什么？",
                        elem_classes=["example-button"]
                    )

                    gr.HTML(
                        """
                        <div class="info-box" style="margin-top: 18px;">
                            <strong>系统能力</strong><br>
                            1. 本地保险资料检索<br>
                            2. 条款内容归纳总结<br>
                            3. 保障范围对比说明<br>
                            4. 面向业务场景的问答
                        </div>
                        """
                    )

                    gr.HTML(
                        """
                        <div class="info-box" style="margin-top: 12px;">
                            <strong>演示建议</strong><br>
                            可直接询问具体保险产品、保障责任、理赔材料、适用场景等问题。
                        </div>
                        """
                    )

                    clear_btn = gr.Button(
                        "清空对话",
                        variant="secondary"
                    )

            user_input.submit(
                chat_response,
                inputs=[user_input, agent_state],
                outputs=[user_input, agent_state, chatbot]
            )

            submit_btn.click(
                chat_response,
                inputs=[user_input, agent_state],
                outputs=[user_input, agent_state, chatbot]
            )

            for btn, question in [
                (example_1, "介绍一下雇主责任险"),
                (example_2, "雇主责任险主要保障哪些内容？"),
                (example_3, "施工保适合什么业务场景？"),
                (example_4, "发生工伤事故时理赔流程是什么？"),
            ]:
                btn.click(
                    fn=lambda q=question: q,
                    inputs=[],
                    outputs=user_input
                ).then(
                    chat_response,
                    inputs=[user_input, agent_state],
                    outputs=[user_input, agent_state, chatbot]
                )

            clear_btn.click(
                clear_chat,
                inputs=[],
                outputs=[user_input, agent_state, chatbot]
            )

        print("Web 界面准备就绪，正在启动服务...")

        demo.launch(
            server_name="127.0.0.1",
            server_port=7861,
            inbrowser=True,
            show_error=True
        )

    except Exception as e:
        print(f"启动 Web 界面失败: {str(e)}")
        print("请检查网络连接和 API Key 配置")


if __name__ == '__main__':
    load_local_env()
    ensure_localhost_no_proxy()
    # 运行模式选择
    app_gui()          # 图形界面模式（默认）
    # app_tui() 
