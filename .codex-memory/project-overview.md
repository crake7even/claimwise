# 项目概览

## 项目背景

本项目是保险资料智能问答系统，用于围绕保险产品、保障范围、理赔流程、行业信息等内容进行 AI 检索问答。

项目从 PDF 课程案例升级而来，核心覆盖：

- Elasticsearch 检索
- Qwen embedding 语义召回
- Tavily 外部搜索
- Qwen 流式回答
- React/Vite 前端聊天 UI

## 目录结构

```text
E:\.1BAOxianAgent
├─ frontend
├─ backend
├─ docs
│  ├─ product
│  └─ design
├─ AGENTS.md
├─ README.md
└─ .codex-memory
```

## 项目文档

- 产品文档：`docs\product`
- 当前 MVP：`docs\product\mvp.md`
- 当前 Spec：`docs\product\specs\mvp-spec.md`
- 设计资料：`docs\design`
- 设计参考图：`docs\design\reference\screen.png`
- 后端运行时资料库：`backend\docs`，不要移动到 `docs\product`。

## 前端

- 目录：`frontend`
- 技术栈：React 19、Vite、Tailwind CSS、lucide-react、Base UI Select
- 当前 UI：左侧工作台侧边栏 + 右侧主聊天区
- 已实现：
  - 侧边栏收起/展开
  - 侧边栏自适应影响主界面宽度
  - 底部输入框
  - `快速检索 / 语义理解 / 联网搜索` 模式选择
  - 流式回答展示

## 后端

- 目录：`backend`
- 技术栈：FastAPI、OpenAI compatible client、Qwen/DashScope、Elasticsearch、Tavily
- API：
  - `GET /api/health`
  - `POST /api/chat`
- 后端入口：`backend\api_server.py`
- RAG 核心：`backend\rag_upgrade\HybridRagService`

## 核心模式

- `快速检索`：对应 `quick`，优先使用 Elasticsearch 和本地 BM25。
- `语义理解`：对应 `semantic`，在快速检索基础上使用 Qwen embedding。
- `联网搜索`：对应 `web`，启用外部搜索源补充本地资料。

## 敏感配置

真实密钥和密码位于 `backend\.env`。记忆文件不能记录其中的真实值。
