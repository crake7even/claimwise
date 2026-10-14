from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

RETRIES = 2
RETRY_DELAY_SECONDS = 1.0


class DashScopeReranker:
    """DashScope 文本重排（qwen3.7-text-rerank）：对融合后的候选按问题相关度重新排序。"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        self.model = os.getenv("RERANK_MODEL", "qwen3.7-text-rerank")
        self.endpoint = os.getenv(
            "RERANK_API_URL",
            "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        )
        self.enabled = bool(self.api_key)
        self.status = "ready" if self.enabled else "DASHSCOPE_API_KEY is missing"

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]] | None:
        """返回 [(原始下标, 相关度)]，按相关度降序；失败时返回 None，由调用方回退到融合排序。"""
        if not self.enabled or not documents:
            return None
        payload = {
            "model": self.model,
            "input": {"query": query, "documents": documents},
            "parameters": {"top_n": min(top_n, len(documents)), "return_documents": False},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        body = None
        for attempt in range(RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                # 4xx 为请求或鉴权问题，重试无意义；5xx 视为服务端暂时故障
                self.status = f"rerank HTTP {exc.code}"
                if exc.code < 500 or attempt == RETRIES:
                    return None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                # DNS 解析失败、握手超时等网络抖动，短暂等待后重试
                self.status = f"rerank failed: {type(exc).__name__}: {exc}"
                if attempt == RETRIES:
                    return None
            except Exception as exc:
                self.status = f"rerank failed: {type(exc).__name__}: {exc}"
                return None
            time.sleep(RETRY_DELAY_SECONDS)
        results = (body.get("output") or {}).get("results") or []
        self.status = "ready"
        return [(int(item["index"]), float(item["relevance_score"])) for item in results]
