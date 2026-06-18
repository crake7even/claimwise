# 常用命令

## 启动后端

```powershell
cd "E:\.1BAOxianAgent\backend"
.\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 7870
```

## 后端健康检查

浏览器访问：

```text
http://127.0.0.1:7870/api/health
```

或 PowerShell：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:7870/api/health" | ConvertTo-Json
```

## 启动前端

```powershell
cd "E:\.1BAOxianAgent\frontend"
npm run dev
```

访问：

```text
http://127.0.0.1:3000/
```

## 前端验证

```powershell
cd "E:\.1BAOxianAgent\frontend"
npm run build
npm run lint
```

## 后端 CLI 验证

```powershell
cd "E:\.1BAOxianAgent\backend"
.\.venv\Scripts\python.exe ai_bot-6.py --cli --query "介绍下雇主责任险"
```

## Elasticsearch

如果需要真实 ES 检索，先启动本机 Elasticsearch。密码配置在 `backend\.env`，不要打印或写入记忆。
