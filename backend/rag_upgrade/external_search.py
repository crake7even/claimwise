from __future__ import annotations

from dataclasses import dataclass
import json
import os
import urllib.error
import urllib.request


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
    """博查 Web Search API（国内联网搜索），返回结构化的标题、链接和摘要。"""

    def __init__(self):
        self.api_key = os.getenv("BOCHA_API_KEY", "").strip()
        self.endpoint = os.getenv("BOCHA_API_URL", "https://api.bochaai.com/v1/web-search")
        self.freshness = os.getenv("BOCHA_FRESHNESS", "noLimit")
        self.status = "disabled" if not self.api_key else "ready"

    def search(self, query: str, top_k: int = 3) -> list[ExternalHit]:
        if not self.api_key:
            self.status = "BOCHA_API_KEY is missing"
            return []
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
                title=item.get("name", ""),
                url=item.get("url", ""),
                content=item.get("summary") or item.get("snippet", ""),
                score=1.0 / (rank + 1),
                provider="bocha_web_search",
            ))
        return hits
