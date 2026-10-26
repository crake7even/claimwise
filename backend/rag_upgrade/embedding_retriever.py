from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path

from openai import OpenAI

from .config import EMBEDDING_CACHE, env_int
from .document_loader import DocChunk
from .keyword_retriever import RetrievalHit


class EmbeddingRetriever:
    def __init__(
        self,
        chunks: list[DocChunk],
        cache_path: Path = EMBEDDING_CACHE,
        model: str = "text-embedding-v4",
        dimensions: int = 1024,
    ):
        self.chunks = chunks
        self.cache_path = cache_path
        self.model = model
        self.dimensions = dimensions
        self.status = "disabled"
        self.enabled = bool(os.getenv("DASHSCOPE_API_KEY", "").strip())
        self._vectors: dict[str, list[float]] = {}
        self._ready = False
        self._query_cache: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        if self.enabled:
            self.status = "ready"

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            timeout=20,
            max_retries=0,
        )

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if data.get("model") != self.model or data.get("dimensions") != self.dimensions:
            return
        vectors = data.get("vectors", {})
        if isinstance(vectors, dict):
            self._vectors = {key: value for key, value in vectors.items() if isinstance(value, list)}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self.model,
            "dimensions": self.dimensions,
            "vectors": self._vectors,
        }
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _embed(self, texts: list[str]) -> list[list[float]]:
        with self._client() as client:
            response = client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        return [item.embedding for item in response.data]

    def ensure_index(self, batch_size: int = 10) -> bool:
        if not self.enabled:
            self.status = "DASHSCOPE_API_KEY is missing"
            return False
        if self._ready:
            return True
        with self._lock:
            if self._ready:
                return True
            return self._build_index(batch_size)

    def _build_index(self, batch_size: int) -> bool:
        self._load_cache()
        current_ids = {chunk.id for chunk in self.chunks}
        stale = [key for key in self._vectors if key not in current_ids]
        for key in stale:
            self._vectors.pop(key)
        missing = [chunk for chunk in self.chunks if chunk.id not in self._vectors]
        if not missing:
            if stale:
                self._save_cache()
            self.status = f"loaded {len(self._vectors)} embeddings"
            self._ready = True
            return True

        try:
            for start in range(0, len(missing), batch_size):
                batch = missing[start:start + batch_size]
                vectors = self._embed([chunk.content[:8000] for chunk in batch])
                for chunk, vector in zip(batch, vectors):
                    self._vectors[chunk.id] = vector
            self._save_cache()
            self.status = f"indexed {len(self._vectors)} embeddings"
            self._ready = True
            return True
        except Exception as exc:
            self.status = f"embedding failed: {type(exc).__name__}: {exc}"
            return False

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def embed_query(self, query: str) -> list[float] | None:
        """查询向量带缓存，可提前调用预热（与查询改写并行）。"""
        cached = self._query_cache.get(query)
        if cached is not None:
            return cached
        try:
            vector = self._embed([query])[0]
        except Exception as exc:
            self.status = f"query embedding failed: {type(exc).__name__}: {exc}"
            return None
        if len(self._query_cache) >= 256:
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[query] = vector
        return vector

    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        if not self.ensure_index():
            return []
        query_vector = self.embed_query(query)
        if query_vector is None:
            return []

        hits: list[RetrievalHit] = []
        chunk_by_id = {chunk.id: chunk for chunk in self.chunks}
        for chunk_id, vector in self._vectors.items():
            chunk = chunk_by_id.get(chunk_id)
            if not chunk:
                continue
            score = self._cosine(query_vector, vector)
            hits.append(RetrievalHit(
                source=chunk.source,
                file_name=chunk.file_name,
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=score,
                retriever="qwen_embedding",
                section=chunk.section,
            ))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]


def build_embedding_retriever(chunks: list[DocChunk]) -> EmbeddingRetriever:
    return EmbeddingRetriever(
        chunks=chunks,
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-v4"),
        dimensions=env_int("EMBEDDING_DIMENSIONS", 1024),
    )
