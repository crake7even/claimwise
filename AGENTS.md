# 项目协作规则

默认中文回答，代码、变量名、命令、技术术语保留英文。

处理本项目时：

- 先确认目标，再修改文件。
- 只改当前任务需要的内容，不顺手重构无关代码。
- 前端 UI 修改不能破坏现有 `/api/chat`、`/api/health` 调用。
- 后端检索逻辑、`.env` 配置、ES、DashScope、Tavily 相关行为不能随意改动。
- 涉及 API Key、密码、Token、私钥、数据库凭据时，只记录它们放在哪里，不记录真实值。
- 不要在日志、README、项目记忆或回答中打印 `backend\.env` 的敏感内容。
- 更新 `.codex-memory` 前，先给出记忆草案，等用户确认后再写入。
- 新对话继续项目时，先读取 `AGENTS.md` 和 `.codex-memory\INDEX.md`，再按任务读取具体记忆文件。

常用入口：

- 前端目录：`E:\.1BAOxianAgent\frontend`
- 后端目录：`E:\.1BAOxianAgent\backend`
- 设计参考：`E:\.1BAOxianAgent\docs\design`
- 项目记忆：`E:\.1BAOxianAgent\.codex-memory`
