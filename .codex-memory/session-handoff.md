# 会话交接

## 当前状态

- 项目已按 Vibe Coding + Codex 记忆流程整理目录边界。
- 正式产品文档已放入 `docs\product`。
- 设计资料已从顶层设计参考目录迁移到 `docs\design`。
- 后端运行时资料库仍保持在 `backend\docs`，未移动。
- 前端和后端业务源码未改动。
- 前端 UI 保持左侧工作台侧边栏 + 右侧主聊天区布局。
- 后端保留 ES、Qwen embedding、Tavily、Qwen 流式回答能力。

## 当前有效文档

- Milestones：`docs\product\milestones.md`
- MVP：`docs\product\mvp.md`
- MVP Spec：`docs\product\specs\mvp-spec.md`
- 设计说明：`docs\design\README.md`
- 设计参考图：`docs\design\reference\screen.png`

## 已验证

- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- 后端 `/api/health` 返回 `chunks=43`，`quick / semantic / web` 均可用。
- 前端页面访问返回 HTTP `200`。
- `quick / semantic / web` 三种 mode 均可发起问答并返回非空响应。
- 临时验证服务已关闭，未保留 `3000/7870` 监听进程。

## 下次继续优先事项

1. 如继续产品流程，先读取 `docs\product\specs\mvp-spec.md` 做验收依据。
2. 如继续研发流程，保持不改动 `backend\docs`、`.env`、ES、DashScope、Tavily 相关行为，除非任务明确要求。
3. 可进一步复检问答质量或规划下一个已确认 Milestone。

## 注意

- `backend\.env` 已作为本机运行配置保留，但不要读取或输出其中真实密钥。
- 如果后续要上传公开仓库或发给别人，必须先移除 `backend\.env`。
