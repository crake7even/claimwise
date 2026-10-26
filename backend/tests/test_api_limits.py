from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


with patch.dict(os.environ, {
    "ENABLE_ES": "false",
    "ENABLE_EMBEDDING": "false",
    "DASHSCOPE_API_KEY": "",
    "BOCHA_API_KEY": "",
}):
    import api_server

from api_limits import ApiLimits, LimitExceeded


def verified_retrieval() -> dict:
    return {
        "reranked": True, "rewritten": None,
        "sources": [{"id": 1, "kind": "local", "title": "测试条款", "section": "", "snippet": "保险责任", "score": 0.9}],
    }


class ApiLimitsTests(unittest.TestCase):
    def limits(self, **overrides):
        return ApiLimits(**({
            "per_ip_per_minute": 6,
            "global_per_minute": 30,
            "daily_requests": 200,
            "max_concurrent": 4,
        } | overrides))

    def test_ip_limit_and_minute_reset(self):
        limits = self.limits(per_ip_per_minute=1)
        limits.acquire("first", now=120)
        limits.release()
        with self.assertRaises(LimitExceeded) as raised:
            limits.acquire("first", now=121)
        self.assertEqual(raised.exception.retry_after, 59)
        limits.acquire("second", now=121)
        limits.release()
        limits.acquire("first", now=180)
        limits.release()

    def test_global_limit_cannot_be_bypassed_with_new_ips(self):
        limits = self.limits(global_per_minute=1)
        limits.acquire("first", now=120)
        limits.release()
        with self.assertRaises(LimitExceeded):
            limits.acquire("second", now=121)

    def test_daily_budget_is_not_refunded_and_resets_at_utc_midnight(self):
        limits = self.limits(daily_requests=1)
        limits.acquire("first", now=120)
        limits.release()
        with self.assertRaises(LimitExceeded):
            limits.acquire("second", now=180)
        limits.acquire("second", now=86400)
        limits.release()

    def test_concurrent_budget_reservations_are_atomic(self):
        limits = self.limits(daily_requests=1)
        def attempt(index):
            try:
                limits.acquire(str(index), now=120)
            except LimitExceeded:
                return False
            limits.release()
            return True
        with ThreadPoolExecutor(max_workers=8) as pool:
            accepted = list(pool.map(attempt, range(20)))
        self.assertEqual(sum(accepted), 1)

    def test_rejected_concurrency_does_not_consume_budget(self):
        limits = self.limits(max_concurrent=1, daily_requests=2)
        limits.acquire("first", now=120)
        with self.assertRaises(LimitExceeded):
            limits.acquire("second", now=120)
        limits.release()
        limits.acquire("second", now=120)
        limits.release()


class ApiProtectionTests(unittest.TestCase):
    def test_forwarded_header_cannot_bypass_ip_limit(self):
        limits = ApiLimits(1, 30, 200, 4)
        with patch.object(api_server, "api_limits", limits), \
                patch.object(api_server, "retrieve", return_value={"rewritten": None, "sources": []}), \
                TestClient(api_server.app) as client:
            self.assertEqual(client.post("/api/search", json={"query": "q"}, headers={"X-Forwarded-For": "192.0.2.1"}).status_code, 200)
            self.assertEqual(client.post("/api/search", json={"query": "q"}, headers={"X-Forwarded-For": "192.0.2.2"}).status_code, 429)

    def test_both_endpoints_share_budget_before_retrieval(self):
        limits = ApiLimits(6, 30, 1, 4)
        with patch.object(api_server, "api_limits", limits), \
                patch.object(api_server, "retrieve") as retrieve:
            retrieve.return_value = {"rewritten": None, "sources": []}
            with TestClient(api_server.app) as client:
                self.assertEqual(client.post("/api/search", json={"query": "q"}).status_code, 200)
                response = client.post("/api/chat", json={"message": "q"})
                self.assertEqual(response.status_code, 429)
                self.assertGreater(int(response.headers["retry-after"]), 0)
                self.assertEqual(client.get("/api/health").status_code, 200)
            retrieve.assert_called_once()

    def test_concurrency_slot_covers_entire_stream(self):
        limits = ApiLimits(6, 30, 200, 1)
        started = threading.Event()
        finish = threading.Event()
        def stream(*args):
            started.set()
            if not finish.wait(timeout=5):
                raise RuntimeError("test stream timed out")
            yield api_server.event("done")
        with patch.object(api_server, "api_limits", limits), \
                patch.object(api_server, "stream_answer", side_effect=stream), \
                patch.object(api_server, "retrieve") as retrieve, \
                TestClient(api_server.app) as client, \
                ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(client.post, "/api/chat", json={"message": "q"})
            try:
                self.assertTrue(started.wait(timeout=5))
                self.assertEqual(client.post("/api/search", json={"query": "q"}).status_code, 429)
                retrieve.assert_not_called()
            finally:
                finish.set()
            self.assertEqual(pending.result(timeout=5).status_code, 200)
            retrieve.return_value = {"rewritten": None, "sources": []}
            self.assertEqual(client.post("/api/search", json={"query": "q"}).status_code, 200)

    def test_slot_is_released_after_retrieval_exception(self):
        limits = ApiLimits(6, 30, 200, 1)
        with patch.object(api_server, "api_limits", limits), \
                patch.object(api_server, "retrieve", side_effect=RuntimeError("test")), \
                TestClient(api_server.app, raise_server_exceptions=False) as client:
            self.assertEqual(client.post("/api/search", json={"query": "q"}).status_code, 500)
            self.assertEqual(client.post("/api/search", json={"query": "q"}).status_code, 500)

    def test_generation_has_output_limit_and_closes_upstream(self):
        client = MagicMock()
        response = MagicMock()
        response.__iter__.return_value = iter([])
        client.chat.completions.create.return_value = response
        with patch.object(api_server, "qwen_client", return_value=client), \
                patch.object(api_server, "retrieve", return_value=verified_retrieval()):
            list(api_server.stream_answer("雇主责任险保障什么", "quick"))
        self.assertEqual(client.chat.completions.create.call_args.kwargs["max_tokens"], 1024)
        response.close.assert_called_once()
        client.close.assert_called_once()

    def test_output_limit_marks_answer_as_incomplete(self):
        client = MagicMock()
        response = MagicMock()
        response.__iter__.return_value = iter([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="partial"), finish_reason="length")]),
        ])
        client.chat.completions.create.return_value = response
        with patch.object(api_server, "qwen_client", return_value=client), \
                patch.object(api_server, "retrieve", return_value=verified_retrieval()):
            events = "".join(api_server.stream_answer("雇主责任险保障什么", "quick"))
        self.assertIn("回答达到长度上限", events)
        response.close.assert_called_once()

    def test_broken_response_connection_closes_generation_stream(self):
        client = MagicMock()
        upstream = MagicMock()
        upstream.__iter__.return_value = iter([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="partial"))]),
        ])
        client.chat.completions.create.return_value = upstream
        async def run():
            response = api_server.ChatStreamingResponse(api_server.stream_answer("雇主责任险保障什么", "quick"))
            async def receive():
                await asyncio.Future()
            async def send(message):
                if message["type"] == "http.response.body" and b'"delta"' in message["body"]:
                    raise RuntimeError("connection closed")
            with self.assertRaises(Exception):
                await response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send)
        with patch.object(api_server, "qwen_client", return_value=client), \
                patch.object(api_server, "retrieve", return_value=verified_retrieval()):
            asyncio.run(run())
        upstream.close.assert_called_once()
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
