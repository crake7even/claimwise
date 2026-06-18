# Ecommerce Search Strategy Demo

## Positioning

This module turns the course search project into a Shopee-style ecommerce search strategy demo. It focuses on the JD keywords: query intent recognition, recall, relevance matching, product experience, AI landing in ecommerce search, and basic data analysis.

## Run

Use the bundled Python or your local Python from the project root:

```powershell
python -m commerce_search.data_loader
python -m commerce_search.search_service "budget samsung phone" --top-k 5
python -m commerce_search.evaluate_search
python -m commerce_search.smoke_test
```

Optional Gradio UI:

```powershell
python -m commerce_search.app --gui
```

If `gradio` is not installed, use the CLI path first.

No-dependency web demo:

```powershell
python -m commerce_search.web_demo --port 7860
```

Open `http://127.0.0.1:7860`.

## Data

- Built-in seed data covers phone accessories, audio, computers, fashion, beauty, home appliances, home, groceries, and toys.
- If available, the module also reads `E:\.Dve\Learning\shopee-search-internship\scripts\data\ecommerce.json` and imports a 3C product subset.

## Search Flow

1. Clean and tokenize the query.
2. Detect intent: brand, category, attribute, price, promotion, scenario, or broad.
3. Recall candidates with local BM25/field matching.
4. Add semantic expansion from the intent dictionary.
5. Rerank with business features: popularity, sales, rating, price bias, and promotion match.
6. Return explainable results and offline evaluation metrics.

## Qwen Enhancement

The default path does not require an API key. After you create `.env` and install the optional `openai` package, Qwen can be enabled for query understanding experiments:

```powershell
python -m commerce_search.search_service "cheap laptop for school" --top-k 5 --use-qwen
```

When `DASHSCOPE_API_KEY` is missing, the code falls back to local rules and still runs.

## Manual Operations

- Create `.env` only when you want Qwen/DashScope enhancement.
- Docker and Elasticsearch are not required for the current local smoke-test version.
- Do not commit `.env`; it is ignored by `.gitignore`.
