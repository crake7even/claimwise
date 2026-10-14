from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
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
        # (期望文件片段, 允许的最大排名)。"企业团体意外险"与雇主责任险 FAQ 中"团体意外险"字面高度重合，
        # 纯 BM25 下允许落在前 3；整体召回质量以 eval/ 评测集为准。
        cases = {
            "雇主责任险保障什么": ("雇主责任险", 1),
            "施工保的保险责任": ("施工保", 1),
            "财产一切险保障范围": ("财产一切险", 1),
            "企业团体意外险": ("企业团体综合意外险", 3),
        }
        for query, (expected_file_fragment, max_rank) in cases.items():
            with self.subTest(query=query):
                result = self.service.search(
                    query,
                    top_k=3,
                    use_es=False,
                    use_embedding=False,
                    use_external=False,
                )
                self.assertTrue(result["contexts"])
                top_files = [context["file_name"] for context in result["contexts"][:max_rank]]
                self.assertTrue(any(expected_file_fragment in name for name in top_files), top_files)


class DocumentLoadingTests(unittest.TestCase):
    def test_short_and_unreadable_documents_are_skipped_with_report(self) -> None:
        from rag_upgrade import document_loader

        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "ok.txt").write_text("雇主责任险" * 100, encoding="utf-8")
            (docs / "short.txt").write_text("太短", encoding="utf-8")
            (docs / "scan.pdf").write_bytes(b"%PDF-1.4")
            with patch.object(document_loader, "read_pdf", side_effect=document_loader.PdfSupportMissing("pdfplumber is not installed")), \
                    self.assertLogs("rag_upgrade.document_loader", level="WARNING") as logs:
                chunks, report = document_loader.load_corpus(docs)

        status = {item["file"]: item["status"] for item in report}
        self.assertEqual(status["ok.txt"], "loaded")
        self.assertTrue(status["short.txt"].startswith("skipped: text too short"))
        self.assertEqual(status["scan.pdf"], "skipped: pdfplumber is not installed")
        self.assertEqual({chunk.file_name for chunk in chunks}, {"ok.txt"})
        self.assertEqual(len(logs.records), 2)

    def test_real_corpus_loads_every_document(self) -> None:
        with patch.dict(os.environ, OFFLINE_ENV, clear=False):
            service = HybridRagService()
        skipped = [doc["file"] for doc in service.documents if doc["status"] != "loaded"]
        self.assertEqual(skipped, [])


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


class RerankerRetryTests(unittest.TestCase):
    def _reranker(self):
        from rag_upgrade.reranker import DashScopeReranker

        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
            return DashScopeReranker()

    def test_retries_transient_network_error(self) -> None:
        import urllib.error

        response = MagicMock()
        response.read.return_value = json.dumps({"output": {"results": [{"index": 1, "relevance_score": 0.9}]}}).encode()
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", side_effect=[urllib.error.URLError("dns"), response]) as urlopen, \
                patch("rag_upgrade.reranker.time.sleep"):
            ranked = self._reranker().rerank("q", ["a", "b"], top_n=2)
        self.assertEqual(ranked, [(1, 0.9)])
        self.assertEqual(urlopen.call_count, 2)

    def test_does_not_retry_client_error(self) -> None:
        import urllib.error

        error = urllib.error.HTTPError("url", 401, "unauthorized", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as urlopen, patch("rag_upgrade.reranker.time.sleep"):
            reranker = self._reranker()
            self.assertIsNone(reranker.rerank("q", ["a"], top_n=1))
        self.assertEqual(urlopen.call_count, 1)
        self.assertIn("401", reranker.status)


class ApiContractTests(unittest.TestCase):
    def test_health_reports_offline_capabilities_truthfully(self) -> None:
        status = api_server.health()
        self.assertTrue(status["ok"])
        self.assertTrue(status["quick"])
        self.assertFalse(status["semantic"])
        self.assertFalse(status["web"])
        self.assertTrue(all({"file", "chars", "chunks", "status"} <= doc.keys() for doc in status["documents"]))

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

    def test_search_endpoint_returns_structured_sources(self) -> None:
        body = api_server.search(api_server.SearchRequest(query="施工保投保要求", mode="quick", top_k=3))
        self.assertEqual(len(body["results"]), 3)
        first = body["results"][0]
        self.assertEqual(first["id"], 1)
        self.assertEqual(first["kind"], "local")
        self.assertIn("施工保", first["title"])


def parse_events(stream) -> list[dict]:
    return [json.loads(line) for line in "".join(stream).splitlines() if line.strip()]


class StreamAnswerTests(unittest.TestCase):
    def test_offline_stream_emits_sources_then_fallback(self) -> None:
        events = parse_events(api_server.stream_answer("雇主责任险保障什么", "quick"))
        self.assertEqual([e["type"] for e in events], ["sources", "delta", "done"])
        self.assertTrue(events[0]["sources"])
        self.assertIn("DASHSCOPE_API_KEY", events[1]["text"])

    def test_no_context_returns_fixed_answer_without_calling_model(self) -> None:
        empty = {"query": "q", "queries": ["q"], "status": {}, "reranked": True, "contexts": [], "external": []}
        with patch.object(api_server.service, "search", return_value=empty), \
                patch.object(api_server, "qwen_client") as client:
            events = parse_events(api_server.stream_answer("今天天气怎么样", "quick"))
        client.assert_not_called()
        self.assertEqual(events[0], {"type": "sources", "sources": [], "rewritten": None})
        self.assertEqual(events[1]["text"], api_server.NO_CONTEXT_ANSWER)

    def test_low_rerank_scores_are_filtered(self) -> None:
        result = {
            "query": "q", "queries": ["q"], "status": {}, "reranked": True, "external": [],
            "contexts": [
                {"file_name": "a.txt", "section": "", "content": "x", "rerank_score": 0.9},
                {"file_name": "b.txt", "section": "", "content": "y", "rerank_score": 0.2},
            ],
        }
        with patch.object(api_server.service, "search", return_value=result):
            retrieved = api_server.retrieve("q", "quick", [], top_k=6)
        self.assertEqual([s["title"] for s in retrieved["sources"]], ["a"])

    def test_web_search_uses_original_question_without_history(self) -> None:
        empty = {"query": "q", "queries": ["q"], "status": {}, "reranked": False, "contexts": [], "external": []}
        prefetched = [object()]
        with patch.object(api_server.rewriter, "rewrite", return_value="改写后的条款查询"), \
                patch.object(api_server.service.external, "search", return_value=prefetched) as web_search, \
                patch.object(api_server.service, "search", return_value=empty) as search:
            api_server.retrieve("无接触交通事故案例", "web", [], top_k=6)
            # 无历史时联网搜索用原问题，并与查询改写并行预取
            web_search.assert_called_once_with("无接触交通事故案例", top_k=3)
            self.assertIs(search.call_args.kwargs["external_hits"], prefetched)
            self.assertEqual(search.call_args.kwargs["external_query"], "无接触交通事故案例")
            history = [{"role": "user", "content": "无接触交通事故案例"}, {"role": "assistant", "content": "..."}]
            api_server.retrieve("上网搜一下", "web", history, top_k=6)
            self.assertEqual(search.call_args.kwargs["external_query"], "改写后的条款查询")
            self.assertIsNone(search.call_args.kwargs["external_hits"])

    def test_generation_error_emits_error_and_fallback(self) -> None:
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("boom")
        with patch.object(api_server, "qwen_client", return_value=client):
            events = parse_events(api_server.stream_answer("雇主责任险保障什么", "quick"))
        types = [e["type"] for e in events]
        self.assertEqual(types, ["sources", "error", "delta", "done"])
        self.assertIn("资料摘要", events[2]["text"])

    def test_history_is_passed_to_model(self) -> None:
        client = MagicMock()
        client.chat.completions.create.return_value = iter([])
        history = [{"role": "user", "content": "雇主责任险保障什么"}, {"role": "assistant", "content": "保障死亡伤残"}]
        with patch.object(api_server, "qwen_client", return_value=client):
            list(api_server.stream_answer("它的保费怎么算", "quick", history))
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertIn("<资料>", messages[-1]["content"])


class RetrievalUnitTests(unittest.TestCase):
    def test_tokenize_generates_bigrams_across_whole_chinese_run(self) -> None:
        from rag_upgrade.keyword_retriever import tokenize

        self.assertEqual(tokenize("酒后驾车ABC"), ["酒后", "后驾", "驾车", "abc"])

    def test_rrf_uses_rank_not_raw_score(self) -> None:
        from rag_upgrade.hybrid_rag import HybridRagService
        from rag_upgrade.keyword_retriever import RetrievalHit

        def hit(chunk_id: int, score: float, retriever: str) -> RetrievalHit:
            return RetrievalHit("s", "f.txt", chunk_id, "c", score, retriever)

        bm25 = [hit(1, 30.0, "local_bm25"), hit(2, 29.0, "local_bm25")]
        embedding = [hit(2, 0.9, "qwen_embedding"), hit(3, 0.8, "qwen_embedding")]
        merged = HybridRagService._merge_hits([bm25, embedding], top_k=3)
        self.assertEqual([item["chunk_id"] for item in merged], [2, 1, 3])

    def test_structured_chunking_splits_articles_and_keeps_chapter(self) -> None:
        from rag_upgrade.document_loader import chunk_structured

        text = "总则\n第一条 " + "甲" * 120 + "\n责任免除\n第八条 " + "乙" * 120
        chunks = chunk_structured(text, "测试条款", max_chars=400)
        self.assertEqual([section for section, _ in chunks], ["总则 第一条", "责任免除 第八条"])
        self.assertTrue(chunks[1][1].startswith("《测试条款》责任免除 第八条"))


if __name__ == "__main__":
    unittest.main()
