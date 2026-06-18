# 前端说明

本目录是保险资料智能问答系统的 React/Vite 前端。

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
