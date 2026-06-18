# 技术决策记录

## 前后端分离

项目采用 React/Vite 前端和 FastAPI 后端分离结构。前端通过 Vite proxy 将 `/api` 转发到 `http://127.0.0.1:7870`。

## 用户友好的模式命名

前端不直接暴露 Elasticsearch、embedding、Tavily 等技术词，改为：

- `快速检索`
- `语义理解`
- `联网搜索`

后端仍使用内部模式值：

- `quick`
- `semantic`
- `web`

## FastAPI 流式接口

后端使用 `POST /api/chat` 返回 `StreamingResponse`，前端逐步读取 response stream，实现回答流式展示。

## 保留真实 `.env`

迁移目标是本机可运行完整包，因此复制 `backend\.env`。但 `.env` 的真实内容不能写入 README、项目记忆或普通回答。

## UI 方向

当前 UI 参考 `docs\design\reference\screen.png` 和 `docs\design\README.md`，采用左侧工作台导航 + 主聊天区布局。参考图中设置、用户、升级、帮助入口已去除。

## 文档与记忆边界

项目按 Vibe Coding + Codex 记忆流程整理边界：

- `docs\product` 保存 Milestone、MVP、Spec 等正式产品文档。
- `docs\design` 保存设计说明和视觉参考。
- `.codex-memory` 只保存索引、当前状态、关键决策、命令和调试经验。
- `backend\docs` 是后端 RAG 运行时资料目录，保持原位，不归入产品文档目录。
