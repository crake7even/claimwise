# Insurance RAG Assistant

> 保险资料智能问答系统

面向保险文档的混合检索 RAG 问答项目，结合 BM25、Elasticsearch、Qwen Embedding 和 Tavily 联网搜索，提供 React/Vite 前端与 FastAPI 流式问答服务。

## 在线地址

- GitHub：[crake7even/insurance-rag-assistant](https://github.com/crake7even/insurance-rag-assistant)
- 在线 Demo：[insurance-rag-frontend.netlify.app](https://insurance-rag-frontend.netlify.app)
- API 健康检查：[insurance-rag-api-hoz9.onrender.com/api/health](https://insurance-rag-api-hoz9.onrender.com/api/health)

## 目录结构

```text
E:\.1BAOxianAgent
├─ frontend          # React / Vite 前端页面
├─ backend           # Python 后端、RAG 检索与运行时资料库
├─ docs              # 产品文档和设计资料
│  ├─ product        # Milestone、MVP、Spec
│  └─ design         # stitch_ai 设计参考
├─ .codex-memory     # Codex 项目记忆
├─ AGENTS.md         # 项目级协作规则
└─ README.md
```

## 启动后端

```powershell
cd "E:\.1BAOxianAgent\backend"
.\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 7870
```

默认后端地址：

```text
http://127.0.0.1:7870
```

健康检查：

```text
http://127.0.0.1:7870/api/health
```

## 启动前端

另开一个 PowerShell：

```powershell
cd "E:\.1BAOxianAgent\frontend"
npm run dev
```

默认访问地址：

```text
http://127.0.0.1:3000/
```

## 验证命令

```powershell
cd "E:\.1BAOxianAgent\frontend"
npm run build
npm run lint
```

## 注意

- `backend\.env` 包含 API Key、Elasticsearch 密码等敏感配置，只能本机使用，不要上传、公开或发给别人。
- 项目记忆只记录敏感配置的位置，不记录任何真实密钥值。
- 产品文档位于 `docs\product`，设计参考位于 `docs\design`。
- `backend\docs` 是后端 RAG 运行时资料目录，不属于产品文档目录。
- 前端通过 `/api` 代理访问后端，请先启动后端再启动前端。
- 如果端口 `3000` 或 `7870` 被占用，需要先关闭原来的服务或调整端口。
