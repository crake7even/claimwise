from __future__ import annotations

import json
import io
import os
import unittest
from unittest.mock import patch
import urllib.error

from rag_upgrade.document_loader import DocChunk, chunk_id
from rag_upgrade.es_retriever import ElasticsearchHTTPRetriever


class ElasticsearchIndexTests(unittest.TestCase):
    def setUp(self):
        self.retriever = ElasticsearchHTTPRetriever("test-insurance")
        self.indices = {}
        self.aliases = {}
        self.bulk_failure = False
        self.alias_failure = False
        self.count_mismatch = False
        self.requests = []
        self.request_patch = patch.object(self.retriever, "_request", side_effect=self.request)
        self.request_patch.start()
        self.addCleanup(self.request_patch.stop)

    def chunk(self, content, index=0):
        return DocChunk(chunk_id("demo.txt", index, content), "demo.txt", "demo.txt", index, content)

    def request(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        if method == "GET" and path == "/":
            return 200, "{}"
        if method == "PUT":
            self.assertNotIn(path[1:], self.indices)
            self.indices[path[1:]] = {}
            return 200, '{"acknowledged": true}'
        if method == "HEAD":
            if path[1:] not in self.indices:
                raise urllib.error.HTTPError(path, 404, "missing", {}, None)
            return 200, ""
        if path.startswith("/_bulk"):
            lines = payload.splitlines()
            items = []
            for offset in range(0, len(lines), 2):
                action = json.loads(lines[offset])["index"]
                if self.bulk_failure:
                    items.append({"index": {"status": 429, "error": {"type": "rejected"}}})
                else:
                    self.indices[action["_index"]][action["_id"]] = json.loads(lines[offset + 1])
                    items.append({"index": {"status": 201}})
            return 200, json.dumps({"errors": self.bulk_failure, "items": items})
        if method == "GET" and path.endswith("/_count"):
            count = len(self.indices[path[1:-len('/_count')]])
            return 200, json.dumps({"count": count - int(self.count_mismatch), "_shards": {"failed": 0}})
        if method == "GET" and path.startswith("/_alias/"):
            alias = path[len('/_alias/'):]
            if alias not in self.aliases:
                raise urllib.error.HTTPError(path, 404, "missing", {}, None)
            return 200, json.dumps({index: {"aliases": {alias: {}}} for index in self.aliases[alias]})
        if path == "/_aliases":
            if self.alias_failure:
                raise urllib.error.HTTPError(path, 403, "forbidden", {}, None)
            for action in payload["actions"]:
                if "remove" in action:
                    item = action["remove"]
                    self.assertTrue(item["must_exist"])
                    self.aliases[item["alias"]].remove(item["index"])
                else:
                    item = action["add"]
                    self.aliases.setdefault(item["alias"], []).append(item["index"])
            return 200, '{"acknowledged": true, "errors": false}'
        if path.endswith("/_search"):
            alias = path[1:-len('/_search')]
            indices = self.aliases.get(alias, [alias])
            hits = [{"_source": value, "_score": 1} for index in indices for value in self.indices[index].values()]
            return 200, json.dumps({"hits": {"hits": hits}})
        raise AssertionError(f"Unexpected request: {method} {path}")

    def test_rebuild_excludes_updated_and_deleted_chunks_and_keeps_old_index(self):
        self.assertTrue(self.retriever.index_chunks([self.chunk("old"), self.chunk("deleted", 1)]))
        self.assertTrue(self.retriever.index_chunks([self.chunk("new")]))
        self.assertEqual([hit.content for hit in self.retriever.search("q")], ["new"])
        self.assertEqual(len(self.indices), 2)
        self.assertFalse(any(method == "DELETE" for method, _, _ in self.requests))

    def test_partial_bulk_failure_keeps_previous_index_readable(self):
        self.assertTrue(self.retriever.index_chunks([self.chunk("old")]))
        self.bulk_failure = True
        self.assertFalse(self.retriever.index_chunks([self.chunk("new")]))
        self.assertEqual([hit.content for hit in self.retriever.search("q")], ["old"])

    def test_partial_bulk_failure_is_not_reported_as_success(self):
        self.bulk_failure = True
        self.assertFalse(self.retriever.index_chunks([self.chunk("new")]))
        self.assertEqual(self.aliases, {})

    def test_malformed_or_inconsistent_bulk_results_do_not_publish(self):
        invalid_results = [
            "not-json",
            '{"errors": false, "items": []}',
            '{"errors": false, "items": [{"index": {"status": 429}}]}',
            '{"errors": false, "items": [{"index": {"status": 201, "error": {}}}]}',
            '{}',
        ]
        for text in invalid_results:
            with self.subTest(response=text):
                def request(method, path, payload=None):
                    if path.startswith("/_bulk"):
                        return 200, text
                    return self.request(method, path, payload)
                with patch.object(self.retriever, "_request", side_effect=request):
                    self.assertFalse(self.retriever.index_chunks([self.chunk("new")]))
                self.assertEqual(self.aliases, {})

    def test_count_mismatch_does_not_switch_alias(self):
        self.assertTrue(self.retriever.index_chunks([self.chunk("old")]))
        self.count_mismatch = True
        self.assertFalse(self.retriever.index_chunks([self.chunk("new")]))
        self.assertEqual([hit.content for hit in self.retriever.search("q")], ["old"])

    def test_alias_failure_keeps_previous_index_readable(self):
        self.assertTrue(self.retriever.index_chunks([self.chunk("old")]))
        self.alias_failure = True
        self.assertFalse(self.retriever.index_chunks([self.chunk("new")]))
        self.assertEqual([hit.content for hit in self.retriever.search("q")], ["old"])

    def test_empty_corpus_does_not_switch_alias(self):
        self.assertFalse(self.retriever.index_chunks([]))
        self.assertEqual(self.requests, [])

    def test_duplicate_ids_do_not_create_index(self):
        chunk = self.chunk("same")
        self.assertFalse(self.retriever.index_chunks([chunk, chunk]))
        self.assertEqual(self.requests, [])

    def test_new_reader_uses_published_alias(self):
        self.assertTrue(self.retriever.index_chunks([self.chunk("new")]))
        reader = ElasticsearchHTTPRetriever("test-insurance")
        with patch.object(reader, "_request", side_effect=self.request):
            self.assertEqual([hit.content for hit in reader.search("q")], ["new"])

    def test_index_script_returns_failure_for_rejected_bulk(self):
        from scripts import index_es

        self.bulk_failure = True
        with patch.object(index_es, "load_dotenv"), \
                patch.dict(os.environ, {"ES_PASSWORD": "test-password"}), \
                patch.object(index_es, "load_chunks", return_value=[self.chunk("new")]), \
                patch.object(index_es, "build_es_retriever", return_value=self.retriever), \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(index_es.main(), 1)


if __name__ == "__main__":
    unittest.main()
