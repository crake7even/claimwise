from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
import json
import os
import threading
import time
import urllib.error
import urllib.request

from .config import env_int
from .web_guard import clamp_query, sanitize_web_text

CACHE_MAX_ENTRIES = 256


@dataclass
class ExternalHit:
    title: str
    url: str
    content: str
    score: float
    provider: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": round(float(self.score), 4),
            "provider": self.provider,
        }


class BochaExternalSearch:
    """博查 Web Search API（国内联网搜索），返回结构化的标题、链接和摘要。
    同一查询在 WEB_SEARCH_CACHE_TTL 秒内复用结果；实际调用次数受 WEB_SEARCH_DAILY_BUDGET 限制（UTC 零点重置）。"""

    def __init__(self):
        self.api_key = os.getenv("BOCHA_API_KEY", "").strip()
        self.endpoint = os.getenv("BOCHA_API_URL", "https://api.bochaai.com/v1/web-search")
        self.freshness = os.getenv("BOCHA_FRESHNESS", "noLimit")
        self.daily_budget = env_int("WEB_SEARCH_DAILY_BUDGET", 100)
        self.cache_ttl = env_int("WEB_SEARCH_CACHE_TTL", 600)
        self.status = "disabled" if not self.api_key else "ready"
        self._lock = threading.Lock()
        self._cache: OrderedDict[tuple[str, int], tuple[float, list[ExternalHit]]] = OrderedDict()
        self._day = -1
        self._day_calls = 0

    def _cached(self, key: tuple[str, int], now: float) -> list[ExternalHit] | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry and now - entry[0] < self.cache_ttl:
                self._cache.move_to_end(key)
                return list(entry[1])
            self._cache.pop(key, None)
            return None

    def _reserve_call(self, now: float) -> bool:
        """占用一次当日调用额度；额度用完返回 False。失败的调用不退还，避免反复重试刷额度。"""
        day = int(now) // 86400
        with self._lock:
            if day != self._day:
                self._day, self._day_calls = day, 0
            if self._day_calls >= self.daily_budget:
                return False
            self._day_calls += 1
            return True

    def search(self, query: str, top_k: int = 3) -> list[ExternalHit]:
        if not self.api_key:
            self.status = "BOCHA_API_KEY is missing"
            return []
        query = clamp_query(query)
        if not query:
            return []
        now = time.time()
        key = (query, top_k)
        cached = self._cached(key, now)
        if cached is not None:
            self.status = "cache hit"
            return cached
        if not self._reserve_call(now):
            self.status = "daily web search budget exhausted"
            return []
        hits = self._request(query, top_k)
        if hits:
            with self._lock:
                self._cache[key] = (now, hits)
                while len(self._cache) > CACHE_MAX_ENTRIES:
                    self._cache.popitem(last=False)
        return list(hits)

    def _request(self, query: str, top_k: int) -> list[ExternalHit]:
        payload = {
            "query": query,
            "freshness": self.freshness,
            "summary": True,
            "count": top_k,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.status = f"Bocha HTTP {exc.code}"
            return []
        except Exception as exc:
            self.status = f"Bocha failed: {type(exc).__name__}: {exc}"
            return []

        if body.get("code") not in (None, 200):
            self.status = f"Bocha error {body.get('code')}: {body.get('msg', '')}"
            return []

        self.status = "searched"
        pages = ((body.get("data") or {}).get("webPages") or {}).get("value") or []
        hits: list[ExternalHit] = []
        for rank, item in enumerate(pages[:top_k]):
            hits.append(ExternalHit(
                title=sanitize_web_text(item.get("name", "")),
                url=item.get("url", ""),
                content=sanitize_web_text(item.get("summary") or item.get("snippet", "")),
                score=1.0 / (rank + 1),
                provider="bocha_web_search",
            ))
        return hits
