from __future__ import annotations

import threading
import time

from starlette.responses import JSONResponse

from rag_upgrade.config import env_int


class LimitExceeded(Exception):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = max(1, retry_after)


class ApiLimits:
    def __init__(self, per_ip_per_minute: int, global_per_minute: int, daily_requests: int, max_concurrent: int):
        if min(per_ip_per_minute, global_per_minute, daily_requests, max_concurrent) < 1:
            raise ValueError("API limits must be positive integers")
        self.per_ip_per_minute = per_ip_per_minute
        self.global_per_minute = global_per_minute
        self.daily_requests = daily_requests
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()
        self._minute = -1
        self._day = -1
        self._clients: dict[str, int] = {}
        self._minute_requests = 0
        self._day_requests = 0
        self._active = 0

    @classmethod
    def from_env(cls) -> ApiLimits:
        return cls(
            env_int("API_REQUESTS_PER_IP_PER_MINUTE", 6),
            env_int("API_REQUESTS_PER_MINUTE", 30),
            env_int("API_REQUESTS_PER_DAY", 200),
            env_int("API_MAX_CONCURRENT", 4),
        )

    def acquire(self, client: str, now: float | None = None) -> None:
        timestamp = int(time.time() if now is None else now)
        minute, day = timestamp // 60, timestamp // 86400
        with self._lock:
            if minute != self._minute:
                self._minute = minute
                self._clients.clear()
                self._minute_requests = 0
            if day != self._day:
                self._day = day
                self._day_requests = 0
            if self._day_requests >= self.daily_requests:
                raise LimitExceeded("今日请求额度已用完，请稍后再试。", 86400 - timestamp % 86400)
            if self._minute_requests >= self.global_per_minute or self._clients.get(client, 0) >= self.per_ip_per_minute:
                raise LimitExceeded("请求过于频繁，请稍后再试。", 60 - timestamp % 60)
            if self._active >= self.max_concurrent:
                raise LimitExceeded("服务繁忙，请稍后再试。", 1)
            self._active += 1
            self._day_requests += 1
            self._minute_requests += 1
            self._clients[client] = self._clients.get(client, 0) + 1

    def release(self) -> None:
        with self._lock:
            self._active -= 1


class ApiLimitsMiddleware:
    def __init__(self, app, get_limits):
        self.app = app
        self.get_limits = get_limits

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        if scope["type"] != "http" or scope["method"] != "POST" or path not in {"/api/chat", "/api/search"}:
            await self.app(scope, receive, send)
            return
        limits = self.get_limits()
        client = scope.get("client")
        try:
            limits.acquire(client[0] if client else "unknown")
        except LimitExceeded as exc:
            response = JSONResponse(
                {"detail": str(exc)}, status_code=429,
                headers={"Retry-After": str(exc.retry_after)},
            )
            await response(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            limits.release()
