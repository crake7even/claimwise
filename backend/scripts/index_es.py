from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from rag_upgrade.config import DOCS_DIR, env_int, load_dotenv
from rag_upgrade.document_loader import load_chunks
from rag_upgrade.es_retriever import build_es_retriever


def main() -> int:
    load_dotenv()
    chunks = load_chunks(
        DOCS_DIR,
        chunk_size=env_int("RAG_CHUNK_SIZE", 1200),
        overlap=env_int("RAG_CHUNK_OVERLAP", 180),
    )
    if not chunks:
        print(f"No chunks loaded from {DOCS_DIR}")
        return 1

    retriever = build_es_retriever(
        index_name=os.getenv("ES_INDEX", "ai_search_insurance_chunks"),
        username=os.getenv("ES_USER", "elastic"),
        password=os.getenv("ES_PASSWORD", ""),
    )
    if not os.getenv("ES_PASSWORD", "").strip():
        print("ES_PASSWORD is missing")
        return 1

    ok = retriever.index_chunks(chunks)
    print(retriever.status)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
