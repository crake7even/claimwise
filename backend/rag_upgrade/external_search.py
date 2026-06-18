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


class TavilyExternalSearch:
    """External data source compatible with the course's Tavily MCP idea.

    The real MCP server can be wired later; this HTTP path keeps the app runnable
    in a normal Windows project without starting an MCP process.
    """

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self.endpoint = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")
        self.status = "disabled" if not self.api_key else "ready"

    def search(self, query: str, top_k: int = 3) -> list[ExternalHit]:
        if not self.api_key:
            self.status = "TAVILY_API_KEY is missing"
            return []
        payload = {
            "query": query,
            "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
            "max_results": top_k,
            "include_answer": False,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
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
            self.status = f"Tavily HTTP {exc.code}"
            return []
        except Exception as exc:
            self.status = f"Tavily failed: {type(exc).__name__}: {exc}"
            return []

        self.status = "searched"
        hits: list[ExternalHit] = []
        for item in body.get("results", [])[:top_k]:
            hits.append(ExternalHit(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", "") or item.get("raw_content", ""),
                score=float(item.get("score") or 0.0),
                provider="tavily_external",
            ))
        return hits
