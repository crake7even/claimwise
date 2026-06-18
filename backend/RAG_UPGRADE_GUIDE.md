# AI Search Upgrade Guide

This project now has a PDF-aligned upgrade entrypoint:

```powershell
.\.venv\Scripts\python.exe ai_bot-6.py
```

CLI smoke test:

```powershell
.\.venv\Scripts\python.exe ai_bot-6.py --cli --query "介绍下雇主责任险"
```

## What Is Covered

- Version2 ES: `rag_upgrade/es_retriever.py` indexes document chunks into Elasticsearch through HTTP APIs and searches by BM25.
- Version3 embedding: `rag_upgrade/embedding_retriever.py` uses DashScope-compatible `text-embedding-v4` for vector recall with local cache.
- Version4 external source: `rag_upgrade/external_search.py` connects to Tavily as the external AI search source.
- Version5 UI: `ai_bot-6.py` provides a Gradio UI with retrieval switches and streaming Qwen answers.

## Manual Steps

Only these runtime steps require manual action:

1. Start Elasticsearch if you want real ES retrieval.
   ```powershell
   .\bin\elasticsearch.bat
   ```
2. Put secrets in `.env`, not in code or logs.
   ```powershell
   DASHSCOPE_API_KEY=your_dashscope_key
   ES_PASSWORD=your_elastic_password
   TAVILY_API_KEY=your_tavily_key
   ```
3. If the ES password is lost, reset it from the Elasticsearch directory.
   ```powershell
   .\bin\elasticsearch-reset-password.bat -u elastic
   ```

If a key or service is missing, `ai_bot-6.py` falls back to local BM25 retrieval and shows status in the UI.
