from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError


OFFLINE_ENV = {
    "ENABLE_ES": "false",
    "ENABLE_EMBEDDING": "false",
    "DASHSCOPE_API_KEY": "",
    "TAVILY_API_KEY": "",
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
