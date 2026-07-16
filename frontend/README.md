# Insurance RAG Assistant Frontend

本目录是 `Insurance RAG Assistant｜保险资料智能问答系统` 的 React/Vite 前端。

- GitHub：[crake7even/insurance-rag-assistant](https://github.com/crake7even/insurance-rag-assistant)
- 在线 Demo：[insurance-rag-frontend.netlify.app](https://insurance-rag-frontend.netlify.app)

## 运行

```powershell
cd "E:\.1BAOxianAgent\frontend"
npm run dev
```

默认访问：

```text
http://127.0.0.1:3000/
```

## 验证

```powershell
cd "E:\.1BAOxianAgent\frontend"
npm run lint
npm run build
```

## 接口约定

- 前端通过 `/api` 访问后端。
- Vite proxy 转发到 `http://127.0.0.1:7870`。
- 现有接口：
  - `GET /api/health`
  - `POST /api/chat`

敏感配置不要写入前端 README 或日志。
