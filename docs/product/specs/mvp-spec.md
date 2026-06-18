# MVP Spec

## 版本目标

整理后的项目保持当前 MVP 功能不变，并将产品文档、设计资料、代码和 Codex 记忆分开维护。

## 用户场景

- 用户在前端输入保险相关问题。
- 用户选择 `快速检索`、`语义理解` 或 `联网搜索`。
- 前端通过 `/api/chat` 向后端发送请求。
- 后端基于本地资料、可选语义召回和可选联网搜索生成流式回答。

## 功能范围

- 保留 React/Vite 前端聊天工作台。
- 保留 FastAPI 后端服务。
- 保留 `GET /api/health` 和 `POST /api/chat`。
- 保留 `quick`、`semantic`、`web` 模式映射。
- 保留 `backend/docs` 作为 RAG 运行时资料目录。
- 新增或整理正式项目文档：
  - `docs/product/milestones.md`
  - `docs/product/mvp.md`
  - `docs/product/specs/mvp-spec.md`
  - `docs/design/README.md`

## 不做什么

- 不修改业务源码逻辑。
- 不移动 `frontend` 或 `backend`。
- 不移动 `backend/docs`。
- 不读取、输出或写入 `backend/.env` 的真实内容。
- 不初始化 Git，不提交代码。
- 不删除本地依赖、构建产物、日志、pid 或缓存。

## 技术实现约束

- 前端 `/api` proxy 继续指向 `http://127.0.0.1:7870`。
- 后端仍从 `backend/.env` 加载本机敏感配置。
- `.codex-memory` 只保存项目记忆和交接，不替代 Spec。
- `docs/product` 保存正式产品文档和开发依据。
- `docs/design` 保存视觉参考和设计说明。

## 验收标准

- 旧的顶层设计参考目录不再作为正式目录存在。
- 设计参考文件位于 `docs/design`。
- 根目录 README 和 AGENTS 中不再指向旧设计参考路径。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- 后端 `/api/health` 能返回健康状态，且 `chunks` 仍来自 `backend/docs`。

## 风险

- 如果误移动 `backend/docs`，会影响 RAG 文档加载。
- 如果误改 API 或 Vite proxy，会影响前后端联调。
- 如果把真实密钥写入文档或记忆，会造成敏感信息泄露。
