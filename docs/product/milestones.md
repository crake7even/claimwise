# Milestones

本文档记录当前已确认的产品阶段和验收口径。未确认的新阶段不在这里展开。

## M0：迁移到本地完整项目

状态：已完成初步迁移，待复检。

目标：

- 项目位于 `E:\.1BAOxianAgent`。
- 前端、后端、设计参考和 Codex 项目记忆分开维护。
- 前端保持工作台式聊天界面。
- 后端保持本地保险资料检索、Qwen embedding、Tavily 外部搜索和 Qwen 流式回答能力。

验收标准：

- `frontend` 可运行 React/Vite 页面。
- `backend` 可启动 FastAPI 服务。
- `GET /api/health` 可返回健康状态。
- `POST /api/chat` 可通过 `quick`、`semantic`、`web` 三种模式发起问答。
- 前端 `npm run lint` 和 `npm run build` 通过。

## M1：当前 MVP 复检

状态：下一步建议执行。

目标：

- 确认迁移后目录、文档、设计资料和项目记忆边界清晰。
- 确认整理后的项目不影响现有问答功能。

验收标准：

- 产品文档位于 `docs/product`。
- 设计资料位于 `docs/design`。
- 运行时知识库仍位于 `backend/docs`。
- 前后端验证结果与整理前一致。
