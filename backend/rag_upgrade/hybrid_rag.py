from __future__ import annotations

import os

from .config import DOCS_DIR, env_bool, env_int, load_dotenv
from .document_loader import load_chunks
from .embedding_retriever import build_embedding_retriever, EmbeddingRetriever
from .es_retriever import build_es_retriever, ElasticsearchHTTPRetriever
from .external_search import TavilyExternalSearch
from .keyword_retriever import BM25Retriever, RetrievalHit


class HybridRagService:
    def __init__(self, docs_dir=DOCS_DIR):
        load_dotenv()
        self.docs_dir = docs_dir
        self.chunks = load_chunks(
            docs_dir,
            chunk_size=env_int("RAG_CHUNK_SIZE", 1200),
            overlap=env_int("RAG_CHUNK_OVERLAP", 180),
        )
        self.local = BM25Retriever(self.chunks)
        self.es: ElasticsearchHTTPRetriever | None = None
        self.embedding: EmbeddingRetriever | None = None
        self.external = TavilyExternalSearch()
        self._init_es()
        self._init_embedding()

    def _init_es(self) -> None:
        if not env_bool("ENABLE_ES", True):
            return
        self.es = build_es_retriever(
            index_name=os.getenv("ES_INDEX", "ai_search_insurance_chunks"),
            username=os.getenv("ES_USER", "elastic"),
            password=os.getenv("ES_PASSWORD", ""),
        )
        if os.getenv("ES_PASSWORD", "").strip():
            self.es.index_chunks(self.chunks)
        else:
            self.es.status = "ES_PASSWORD is missing"

    def _init_embedding(self) -> None:
        if not env_bool("ENABLE_EMBEDDING", True):
            return
        self.embedding = build_embedding_retriever(self.chunks)

    def status(self) -> dict:
        return {
            "docs_dir": str(self.docs_dir),
            "chunks": len(self.chunks),
            "local_bm25": "ready",
            "elasticsearch": self.es.status if self.es else "disabled",
            "embedding": self.embedding.status if self.embedding else "disabled",
            "external_search": self.external.status,
        }

    @staticmethod
    def _merge_hits(groups: list[list[RetrievalHit]], top_k: int) -> list[dict]:
        merged: dict[tuple[str, int], dict] = {}
        weights = {
            "elasticsearch_bm25": 1.25,
            "qwen_embedding": 1.15,
            "local_bm25": 1.0,
        }
        for hits in groups:
            for hit in hits:
                key = (hit.source, hit.chunk_id)
                current = merged.setdefault(key, hit.to_dict() | {"merged_score": 0.0, "retrievers": []})
                current["merged_score"] += float(hit.score) * weights.get(hit.retriever, 1.0)
                current["retrievers"].append(hit.retriever)
        results = sorted(merged.values(), key=lambda item: item["merged_score"], reverse=True)
        return results[:top_k]

    def search(
        self,
        query: str,
        top_k: int = 6,
        use_es: bool = True,
        use_embedding: bool = True,
        use_external: bool = True,
    ) -> dict:
        local_hits = self.local.search(query, top_k=top_k)
        es_hits = self.es.search(query, top_k=top_k) if use_es and self.es else []
        embedding_hits = self.embedding.search(query, top_k=top_k) if use_embedding and self.embedding else []
        external_hits = self.external.search(query, top_k=3) if use_external else []
        return {
            "query": query,
            "status": self.status(),
            "contexts": self._merge_hits([es_hits, embedding_hits, local_hits], top_k=top_k),
            "external": [hit.to_dict() for hit in external_hits],
        }
