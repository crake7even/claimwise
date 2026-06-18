from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlparse

from .search_service import CommerceSearchService


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Shopee Search Strategy Demo</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; color: #1f2937; }
    header { padding: 24px 32px; background: #fff; border-bottom: 1px solid #e5e7eb; }
    main { padding: 24px 32px; max-width: 1180px; margin: 0 auto; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .bar { display: grid; grid-template-columns: 1fr 150px 120px; gap: 10px; margin: 20px 0; }
    input, select, button { font-size: 15px; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; }
    button { background: #ee4d2d; color: #fff; border-color: #ee4d2d; cursor: pointer; }
    .panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .chips span { display: inline-block; margin: 4px 6px 0 0; padding: 4px 8px; background: #eef2ff; border-radius: 999px; font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; }
    .product-visual { width: 100%; aspect-ratio: 4 / 3; border-radius: 6px; background: #f1f5f9; display: grid; place-items: center; overflow: hidden; margin-bottom: 12px; }
    .product-visual img { width: 100%; height: 100%; object-fit: contain; background: #fff; }
    .image-fallback { width: 100%; height: 100%; display: grid; place-items: center; color: #94a3b8; font-weight: 700; letter-spacing: 0; }
    .rank { color: #ee4d2d; font-weight: 700; }
    .name { font-weight: 700; margin: 8px 0; }
    .meta { color: #64748b; font-size: 13px; margin: 6px 0; }
    .score { font-family: Consolas, monospace; font-size: 12px; color: #334155; }
    .examples button { margin: 0 8px 8px 0; background: #fff; color: #334155; border-color: #cbd5e1; }
  </style>
</head>
<body>
  <header>
    <h1>Shopee Search Strategy Demo</h1>
    <div>query intent -> recall -> hybrid rerank -> explainable product results</div>
  </header>
  <main>
    <div class="examples">
      <button onclick="setQuery('budget samsung phone')">budget samsung phone</button>
      <button onclick="setQuery('便宜的蓝牙耳机')">便宜的蓝牙耳机</button>
      <button onclick="setQuery('iPhone 15 clear case')">iPhone 15 clear case</button>
      <button onclick="setQuery('oil control sunscreen spf50')">oil control sunscreen spf50</button>
      <button onclick="setQuery('small air fryer for dorm')">small air fryer for dorm</button>
    </div>
    <div class="bar">
      <input id="query" value="budget samsung phone" />
      <select id="mode">
        <option value="hybrid_rerank">hybrid_rerank</option>
        <option value="keyword">keyword</option>
        <option value="semantic">semantic</option>
      </select>
      <button onclick="runSearch()">Search</button>
    </div>
    <section id="intent" class="panel"></section>
    <section id="results" class="grid"></section>
  </main>
  <script>
    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[ch]));
    }
    function productImage(item) {
      if (item.image) {
        return `<div class="product-visual"><img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=&quot;image-fallback&quot;>No image</div>'"></div>`;
      }
      return '<div class="product-visual"><div class="image-fallback">No image</div></div>';
    }
    function setQuery(q) { document.getElementById('query').value = q; runSearch(); }
    async function runSearch() {
      const q = document.getElementById('query').value;
      const mode = document.getElementById('mode').value;
      const res = await fetch(`/search?q=${encodeURIComponent(q)}&mode=${encodeURIComponent(mode)}&top_k=9`);
      const data = await res.json();
      const intent = data.intent;
      document.getElementById('intent').innerHTML = `
        <strong>Intent:</strong> ${intent.intent}<br/>
        <strong>Reason:</strong> ${intent.reason}<br/>
        <strong>Dataset:</strong> ${data.dataset.count} products<br/>
        <div class="chips">${intent.tokens.map(x => `<span>${x}</span>`).join('')}</div>
        <div class="chips">${intent.expanded_terms.map(x => `<span>${x}</span>`).join('')}</div>
      `;
      document.getElementById('results').innerHTML = data.results.map((item, idx) => `
        <article class="card">
          ${productImage(item)}
          <div class="rank">#${idx + 1}</div>
          <div class="name">${escapeHtml(item.name)}</div>
          <div class="meta">${escapeHtml(item.brand)} | ${escapeHtml(item.categories.slice(0, 2).join(' > '))}</div>
          <div class="meta">$${item.price.toFixed(2)} | rating ${item.rating} | sales ${Math.round(item.sales)}</div>
          <div class="score">final ${item.final_score} | keyword ${item.keyword_score} | semantic ${item.semantic_score}</div>
          <p>${escapeHtml(item.rerank_reason)}</p>
        </article>
      `).join('');
    }
    runSearch();
  </script>
</body>
</html>
"""


class SearchHandler(BaseHTTPRequestHandler):
    service = CommerceSearchService()

    def _send(self, status: int, content: str, content_type: str) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, HTML, "text/html")
            return
        if parsed.path == "/search":
            params = parse_qs(parsed.query)
            query = params.get("q", ["budget samsung phone"])[0]
            mode = params.get("mode", ["hybrid_rerank"])[0]
            top_k = int(params.get("top_k", ["9"])[0])
            output = self.service.search(query=query, top_k=top_k, mode=mode)
            self._send(200, json.dumps(output, ensure_ascii=False), "application/json")
            return
        self._send(404, "not found", "text/plain")

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), SearchHandler)
    print(f"Serving on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
