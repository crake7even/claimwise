from __future__ import annotations

import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError


OFFLINE_ENV = {
    "ENABLE_ES": "false",
    "ENABLE_EMBEDDING": "false",
    "DASHSCOPE_API_KEY": "",
    "BOCHA_API_KEY": "",
}

with patch.dict(os.environ, OFFLINE_ENV, clear=False):
    import api_server
    from rag_upgrade import HybridRagService


class HybridRagOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch.dict(os.environ, OFFLINE_ENV, clear=False):
            cls.service = HybridRagService()

    def test_local_corpus_is_loaded(self) -> None:
        self.assertGreaterEqual(len(self.service.chunks), 40)

    def test_representative_queries_recall_expected_document_at_top_one(self) -> None:
        cases = {
            "雇主责任险保障什么": "雇主责任险",
            "施工保的保险责任": "施工保",
            "财产一切险保障范围": "财产一切险",
            "企业团体意外险": "企业团体综合意外险",
        }
        for query, expected_file_fragment in cases.items():
            with self.subTest(query=query):
                result = self.service.search(
                    query,
                    top_k=3,
                    use_es=False,
                    use_embedding=False,
                    use_external=False,
                )
                self.assertTrue(result["contexts"])
                self.assertIn(expected_file_fragment, result["contexts"][0]["file_name"])


class BochaExternalSearchTests(unittest.TestCase):
    def _search(self, body: dict, top_k: int = 2):
        from rag_upgrade.external_search import BochaExternalSearch

        response = MagicMock()
        response.read.return_value = json.dumps(body).encode("utf-8")
        response.__enter__.return_value = response
        with patch.dict(os.environ, {"BOCHA_API_KEY": "test-key"}), \
                patch("urllib.request.urlopen", return_value=response) as urlopen:
            search = BochaExternalSearch()
            hits = search.search("雇主责任险", top_k=top_k)
        return search, hits, urlopen.call_args[0][0]

    def test_parses_web_pages_and_prefers_summary(self) -> None:
        body = {"code": 200, "data": {"webPages": {"value": [
            {"name": "标题1", "url": "https://a.example", "snippet": "片段1", "summary": "摘要1"},
            {"name": "标题2", "url": "https://b.example", "snippet": "片段2"},
            {"name": "标题3", "url": "https://c.example", "snippet": "片段3"},
        ]}}}
        search, hits, request = self._search(body)
        self.assertEqual([hit.title for hit in hits], ["标题1", "标题2"])
        self.assertEqual([hit.content for hit in hits], ["摘要1", "片段2"])
        self.assertEqual(hits[0].provider, "bocha_web_search")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(json.loads(request.data)["count"], 2)
        self.assertEqual(search.status, "searched")

    def test_api_error_code_returns_no_hits(self) -> None:
        search, hits, _ = self._search({"code": 401, "msg": "invalid key"})
        self.assertEqual(hits, [])
        self.assertIn("401", search.status)


class ApiContractTests(unittest.TestCase):
    def test_health_reports_offline_capabilities_truthfully(self) -> None:
        status = api_server.health()
        self.assertTrue(status["ok"])
        self.assertTrue(status["quick"])
        self.assertFalse(status["semantic"])
        self.assertFalse(status["web"])

    def test_health_reports_configured_optional_capabilities(self) -> None:
        embedding = SimpleNamespace(enabled=True)
        with (
            patch.object(api_server.service, "embedding", embedding),
            patch.object(api_server.service.external, "api_key", "configured"),
        ):
            status = api_server.health()
        self.assertTrue(status["semantic"])
        self.assertTrue(status["web"])

    def test_chat_request_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValidationError):
            api_server.ChatRequest(message="test", mode="unknown")

    def test_chat_request_rejects_oversized_message(self) -> None:
        with self.assertRaises(ValidationError):
            api_server.ChatRequest(message="x" * 4001)


if __name__ == "__main__":
    unittest.main()
