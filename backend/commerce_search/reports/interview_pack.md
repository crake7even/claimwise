# Shopee Search Strategy Demo Interview Pack

## Resume Version

- Built a Shopee-style ecommerce search strategy demo on top of a course AI search project, covering query intent recognition, multi-source product data, candidate recall, explainable reranking, and offline evaluation.
- Integrated 700 local products from a 3C ecommerce dataset plus generated multi-category seed products across fashion, beauty, home appliances, groceries, audio, computers, and toys.
- Implemented rule-based query understanding for brand, category, attribute, price, promotion, and scenario intents, with Chinese/English token handling for queries such as `便宜的蓝牙耳机`.
- Built keyword/BM25 recall, semantic expansion recall, and hybrid rerank using category match, price/promotion intent, popularity, sales, and rating features.
- Evaluated 15 hand-labeled queries with Recall@5, NDCG@5, and MRR@5; current hybrid rerank smoke-test result is Recall@5 0.987, NDCG@5 0.986, MRR@5 1.000.

## Core Explanation

The project simulates a vertical ecommerce search pipeline. A user query first goes through query cleaning and intent recognition. The system then recalls candidate products with local BM25 and field matching, adds semantic expansion terms, and reranks candidates with product-side business features. Each result returns an explanation showing which recall source and ranking feature contributed.

## High-Probability Interview Questions

1. Why does this project match a search strategy JD?

It covers the main search loop: query understanding, recall, relevance ranking, product experience, and offline metrics. It is not just a chatbot; the output is a ranked product list with explainable ranking signals.

2. Why not rely only on an LLM?

Search needs predictable latency, controllable ranking, and measurable relevance. I use deterministic rules and BM25 as the stable baseline, then keep Qwen as an optional enhancement for query rewrite or intent explanation.

3. What is the difference between keyword recall and semantic expansion?

Keyword recall matches exact terms and product fields, so it is strong for precise queries like `iPhone 15 case`. Semantic expansion maps user wording to related terms, such as `耳机 -> headphones, earbuds, bluetooth`, which helps long-tail and Chinese/English mixed queries.

4. How do you avoid semantic expansion hurting relevance?

The rerank stage uses category and business guardrails. Expanded terms can add candidates, but final ranking still considers category match, brand/attribute terms, price intent, promotion intent, popularity, sales, and rating.

5. What are the current limitations?

The labels are small and hand-written. A production system should use real query logs, impression/click/add-to-cart/conversion data, richer category taxonomy, online A/B tests, and latency monitoring.

## Demo Commands

```powershell
python -m commerce_search.data_loader
python -m commerce_search.search_service "便宜的蓝牙耳机" --top-k 5
python -m commerce_search.evaluate_search
python -m commerce_search.smoke_test
```

Optional Qwen enhancement:

```powershell
python -m commerce_search.search_service "cheap laptop for school" --top-k 5 --use-qwen
```

If `DASHSCOPE_API_KEY` or the `openai` package is missing, the Qwen path safely falls back to local intent rules.
