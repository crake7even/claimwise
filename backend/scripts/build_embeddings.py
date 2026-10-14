"""离线预计算文档 embedding 并写入 workspace/embedding_cache.json，避免服务启动后首个语义请求冷启动。

部署时在构建阶段执行（见 render.yaml buildCommand）；未配置 DASHSCOPE_API_KEY 时跳过且不报错。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from rag_upgrade.config import DOCS_DIR, env_int, load_dotenv
from rag_upgrade.document_loader import load_chunks
from rag_upgrade.embedding_retriever import build_embedding_retriever


def main() -> int:
    load_dotenv()
    if not os.getenv("DASHSCOPE_API_KEY", "").strip():
        print("DASHSCOPE_API_KEY is missing, skip embedding precompute")
        return 0
    chunks = load_chunks(
        DOCS_DIR,
        chunk_size=env_int("RAG_CHUNK_SIZE", 400),
        overlap=env_int("RAG_CHUNK_OVERLAP", 60),
        strategy=os.getenv("RAG_CHUNK_STRATEGY", "structured"),
    )
    retriever = build_embedding_retriever(chunks)
    ok = retriever.ensure_index()
    print(retriever.status)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
