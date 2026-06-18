# 排错记录

## PowerShell 中文显示

PowerShell 输出中文路径或文件内容时可能出现乱码，但浏览器和 UTF-8 文件本身可能是正常的。判断前端中文是否正常时，以浏览器显示或 UTF-8 读取为准。

## Elasticsearch HTTPS

Elasticsearch 本地使用 `https://localhost:9200`。浏览器直接访问时可能出现证书不受信任提示，这是本地证书问题。项目配置中可通过 `ES_VERIFY_CERTS=false` 忽略证书校验。

## API Key 缺失降级

如果缺少 `DASHSCOPE_API_KEY`，后端会返回检索摘要，而不是调用 Qwen 生成最终答案。

如果缺少 `TAVILY_API_KEY`，联网搜索不可用，但本地资料检索仍可工作。

如果缺少 `ES_PASSWORD`，ES 索引不可用，项目会退回本地 BM25 检索。

## 端口占用

默认端口：

- 前端：`3000`
- 后端：`7870`

如果页面无法访问或 Vite/FastAPI 启动失败，先检查端口是否被旧进程占用。

## 不要泄露敏感信息

排错时不要把 `backend\.env` 的真实值贴到对话、日志、README 或项目记忆中。

