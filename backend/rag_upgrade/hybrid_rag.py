from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os

from .config import DOCS_DIR, env_bool, env_int, load_dotenv
from .document_loader import load_corpus
from .embedding_retriever import build_embedding_retriever, EmbeddingRetriever
from .es_retriever import build_es_retriever, ElasticsearchHTTPRetriever
from .external_search import BochaExternalSearch
from .keyword_retriever import BM25Retriever, RetrievalHit
from .reranker import DashScopeReranker


class HybridRagService:
    def __init__(self, docs_dir=DOCS_DIR):
        load_dotenv()
        self.docs_dir = docs_dir
        self.chunks, self.documents = load_corpus(
            docs_dir,
            chunk_size=env_int("RAG_CHUNK_SIZE", 400),
            overlap=env_int("RAG_CHUNK_OVERLAP", 60),
            strategy=os.getenv("RAG_CHUNK_STRATEGY", "structured"),
        )
        self.local = BM25Retriever(self.chunks)
        self.es: ElasticsearchHTTPRetriever | None = None
        self.embedding: EmbeddingRetriever | None = None
        self.external = BochaExternalSearch()
        self.reranker = DashScopeReranker() if env_bool("ENABLE_RERANK", True) else None
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
        if not os.getenv("ES_PASSWORD", "").strip():
            self.es.status = "ES_PASSWORD is missing"
        elif env_bool("ES_INDEX_ON_STARTUP", False):
            self.es.index_chunks(self.chunks)
        else:
            # 索引由 scripts/index_es.py 离线构建，启动时只检查连通性
            self.es.ping()

    def _init_embedding(self) -> None:
        if not env_bool("ENABLE_EMBEDDING", True):
            return
        self.embedding = build_embedding_retriever(self.chunks)

    def status(self) -> dict:
        return {
            "docs_dir": str(self.docs_dir),
            "chunks": len(self.chunks),
            "documents_loaded": sum(1 for doc in self.documents if doc["status"] == "loaded"),
            "documents_skipped": [doc["file"] for doc in self.documents if doc["status"] != "loaded"],
            "local_bm25": "ready",
            "elasticsearch": self.es.status if self.es else "disabled",
            "embedding": self.embedding.status if self.embedding else "disabled",
            "external_search": self.external.status,
            "rerank": self.reranker.status if self.reranker else "disabled",
        }

    @staticmethod
    def _merge_hits(groups: list[list[RetrievalHit]], top_k: int) -> list[dict]:
        """RRF 融合：各路只看排名不看原始分数，避免 BM25（无上界）淹没余弦相似度（0~1）。"""
        merged: dict[tuple[str, int], dict] = {}
        weights = {
            "elasticsearch_bm25": 1.0,
            "qwen_embedding": 1.0,
            "local_bm25": 1.0,
        }
        rrf_k = env_int("RAG_RRF_K", 60)
        for hits in groups:
            for rank, hit in enumerate(hits, start=1):
                key = (hit.source, hit.chunk_id)
                current = merged.setdefault(key, hit.to_dict() | {"merged_score": 0.0, "retrievers": []})
                current["merged_score"] += weights.get(hit.retriever, 1.0) / (rrf_k + rank)
                current["retrievers"].append(hit.retriever)
        results = sorted(merged.values(), key=lambda item: item["merged_score"], reverse=True)
        return results[:top_k]

    def _rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict] | None:
        if not self.reranker or not candidates:
            return None
        ranked = self.reranker.rerank(query, [item["content"] for item in candidates], top_n=top_k)
        if ranked is None:
            return None
        return [candidates[index] | {"rerank_score": round(score, 4)} for index, score in ranked]

    def search(
        self,
        query: str,
        top_k: int = 6,
        use_es: bool = True,
        use_embedding: bool = True,
        use_external: bool = True,
        use_rerank: bool = False,
        extra_queries: list[str] | None = None,
        embedding_queries: list[str] | None = None,
        rerank_query: str | None = None,
        external_query: str | None = None,
        external_hits: list | None = None,
    ) -> dict:
        """混合检索。extra_queries 为改写后的补充查询，与原查询的各路结果一起做 RRF；
        use_rerank 时对融合后的前 RERANK_CANDIDATES 个候选重排，失败则回退到融合排序。"""
        queries = [query] + [item for item in (extra_queries or []) if item and item != query]
        candidate_k = max(top_k * 3, env_int("RAG_CANDIDATE_K", 20))
        # 各路检索（含联网搜索）互不依赖，并行执行以降低延迟；结果按固定顺序参与 RRF
        tasks = []
        for item in queries:
            tasks.append((self.local.search, item))
            if use_es and self.es:
                tasks.append((self.es.search, item))
            if use_embedding and self.embedding and (embedding_queries is None or item in embedding_queries):
                tasks.append((self.embedding.search, item))
        with ThreadPoolExecutor(max_workers=len(tasks) + 1) as pool:
            futures = [pool.submit(fn, item, top_k=candidate_k) for fn, item in tasks]
            need_external = use_external and external_hits is None  # 调用方已预取联网结果时不再重复搜索
            external_future = pool.submit(self.external.search, external_query or query, top_k=3) if need_external else None
            groups: list[list[RetrievalHit]] = [future.result() for future in futures]
            if external_future:
                external_hits = external_future.result()
        external_hits = external_hits or []

        reranked = False
        if use_rerank:
            candidates = self._merge_hits(groups, top_k=env_int("RERANK_CANDIDATES", 20))
            contexts = self._rerank(rerank_query or query, candidates, top_k)
            reranked = contexts is not None
            if contexts is None:
                contexts = candidates[:top_k]
        else:
            contexts = self._merge_hits(groups, top_k=top_k)
        return {
            "query": query,
            "queries": queries,
            "status": self.status(),
            "reranked": reranked,
            "contexts": contexts,
            "external": [hit.to_dict() for hit in external_hits],
        }
