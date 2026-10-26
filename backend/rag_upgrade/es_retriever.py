from __future__ import annotations

from base64 import b64encode
import json
import ssl
import urllib.error
import urllib.request
from uuid import uuid4

from .config import env_bool, es_base_url
from .document_loader import DocChunk
from .keyword_retriever import RetrievalHit


class ElasticsearchHTTPRetriever:
    def __init__(
        self,
        index_name: str,
        username: str = "elastic",
        password: str = "",
        verify_certs: bool = False,
        request_timeout: int = 8,
    ):
        self.base_url = es_base_url()
        self.index_name = index_name
        self.read_alias = f"{index_name}-read"
        self.username = username
        self.password = password
        self.verify_certs = verify_certs
        self.request_timeout = request_timeout
        self.available = False
        self.status = "not checked"

    def _context(self):
        if self.base_url.startswith("https://") and not self.verify_certs:
            return ssl._create_unverified_context()
        return None

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.username and self.password:
            token = b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, path: str, payload: dict | str | None = None) -> tuple[int, str]:
        data = None
        headers = self._headers()
        if payload is not None:
            if isinstance(payload, str):
                data = payload.encode("utf-8")
                headers["Content-Type"] = "application/x-ndjson"
            else:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(request, timeout=self.request_timeout, context=self._context()) as response:
            return response.status, response.read().decode("utf-8", errors="replace")

    def ping(self) -> bool:
        try:
            self._request("GET", "/")
            self.available = True
            self.status = "connected"
        except urllib.error.HTTPError as exc:
            self.available = False
            self.status = f"HTTP {exc.code}: {exc.reason}"
        except Exception as exc:
            self.available = False
            self.status = f"{type(exc).__name__}: {exc}"
        return self.available

    def _create_index(self, index_name: str) -> bool:
        if not self.ping():
            return False
        mapping = {
            "mappings": {
                "properties": {
                    "content": {"type": "text", "analyzer": "standard"},
                    "file_name": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "chunk_id": {"type": "integer"},
                    "section": {"type": "keyword"},
                }
            }
        }
        try:
            _, text = self._request("PUT", f"/{index_name}", mapping)
            if json.loads(text).get("acknowledged") is not True:
                self.status = "index creation was not acknowledged"
                return False
            return True
        except Exception as exc:
            self.status = f"index create failed: {type(exc).__name__}: {exc}"
            return False

    def index_chunks(self, chunks: list[DocChunk]) -> bool:
        if not chunks:
            self.status = "index build refused: corpus is empty"
            return False
        if len({chunk.id for chunk in chunks}) != len(chunks):
            self.status = "index build refused: duplicate chunk IDs"
            return False
        index_name = f"{self.index_name}-{uuid4().hex}"
        if not self._create_index(index_name):
            return False
        lines: list[str] = []
        for chunk in chunks:
            lines.append(json.dumps({"index": {"_index": index_name, "_id": chunk.id}}, ensure_ascii=False))
            lines.append(json.dumps({
                "content": chunk.content,
                "file_name": chunk.file_name,
                "source": chunk.source,
                "chunk_id": chunk.chunk_id,
                "section": chunk.section,
            }, ensure_ascii=False))
        try:
            _, text = self._request("POST", "/_bulk?refresh=true", "\n".join(lines) + "\n")
            result = json.loads(text)
            items = result.get("items", [])
            if result.get("errors") is not False or len(items) != len(chunks) or any(
                item.get("index", {}).get("status") not in (200, 201) or "error" in item.get("index", {})
                for item in items
            ):
                self.status = "bulk index failed: incomplete or rejected writes; read alias unchanged"
                return False
            _, text = self._request("GET", f"/{index_name}/_count")
            result = json.loads(text)
            if result.get("count") != len(chunks) or result.get("_shards", {}).get("failed", 0):
                self.status = "index count verification failed; read alias unchanged"
                return False
            self._switch_alias(index_name)
            self.status = f"indexed {len(chunks)} chunks into {index_name}; reading via {self.read_alias}"
            return True
        except Exception as exc:
            self.status = f"bulk index failed: {type(exc).__name__}: {exc}"
            return False

    def _switch_alias(self, index_name: str) -> None:
        try:
            _, text = self._request("GET", f"/_alias/{self.read_alias}")
            current = json.loads(text)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            current = {}
        actions = [
            {"remove": {"index": name, "alias": self.read_alias, "must_exist": True}}
            for name in current
        ]
        actions.append({"add": {"index": index_name, "alias": self.read_alias}})
        _, text = self._request("POST", "/_aliases", {"actions": actions})
        result = json.loads(text)
        if result.get("acknowledged") is not True or result.get("errors", False):
            raise RuntimeError("alias switch was not acknowledged or contained failed actions")

    def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        if not self.available and not self.ping():
            return []
        body = {
            "query": {
                "match": {
                    "content": {
                        "query": query,
                        "operator": "or",
                    }
                }
            },
            "size": top_k,
        }
        try:
            _, text = self._request("POST", f"/{self.read_alias}/_search", body)
            response = json.loads(text)
        except Exception as exc:
            self.status = f"search failed: {type(exc).__name__}: {exc}"
            return []

        hits: list[RetrievalHit] = []
        for item in response.get("hits", {}).get("hits", []):
            source = item.get("_source", {})
            hits.append(RetrievalHit(
                source=source.get("source", ""),
                file_name=source.get("file_name", ""),
                chunk_id=int(source.get("chunk_id", 0)),
                content=source.get("content", ""),
                score=float(item.get("_score") or 0.0),
                retriever="elasticsearch_bm25",
                section=source.get("section", ""),
            ))
        return hits


def build_es_retriever(index_name: str, username: str, password: str) -> ElasticsearchHTTPRetriever:
    return ElasticsearchHTTPRetriever(
        index_name=index_name,
        username=username,
        password=password,
        verify_certs=env_bool("ES_VERIFY_CERTS", False),
    )
