# Ecommerce Search Strategy Evaluation

This report compares three retrieval/ranking paths on a small hand-labeled ecommerce query set.

## Dataset Profile

- Products: 700
- Price range: 1.0 - 899.99, avg 267.76
- Top level categories: Cell Phones(602), Fashion(18), Beauty(18), Home Appliances(18), Groceries(18), Home(9)

## Metric Summary

| Mode | Recall@5 | NDCG@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| keyword | 0.960 | 0.963 | 1.000 |
| semantic | 0.973 | 0.977 | 1.000 |
| hybrid_rerank | 0.987 | 0.986 | 1.000 |

## Query Cases

| Query | Expected Intent | Hybrid Intent | Keyword R@5 | Semantic R@5 | Hybrid R@5 | Hybrid Top1 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| budget samsung phone | price_sensitive | price_sensitive | 1.00 | 1.00 | 1.00 | Samsung - Galaxy S4 4G with 16GB Memory T-Mobile Branded Cell Phone Unlocked - White Frost |
| iPhone 15 clear case | brand_exact | brand_exact | 1.00 | 1.00 | 1.00 | Shopee Basics iPhone 15 Clear Shockproof Case |
| wireless headphones for music | attribute_filter | attribute_filter | 0.80 | 1.00 | 1.00 | Noise Cancelling Wireless Headphones |
| portable speaker for travel | attribute_filter | attribute_filter | 0.80 | 1.00 | 1.00 | Portable Mini Bluetooth Speaker |
| cheap laptop for school | price_sensitive | price_sensitive | 1.00 | 1.00 | 1.00 | Student Budget Laptop 14 inch |
| 4k tv for streaming | attribute_filter | attribute_filter | 1.00 | 1.00 | 1.00 | 4K Smart TV for Streaming |
| camera for photo beginner | scenario_need | scenario_need | 1.00 | 1.00 | 1.00 | Beginner Mirrorless Camera Kit |
| gaming keyboard | attribute_filter | attribute_filter | 1.00 | 1.00 | 1.00 | Gaming Mechanical Keyboard RGB |
| home office printer | scenario_need | scenario_need | 1.00 | 1.00 | 1.00 | Home Office Wireless Printer |
| bluetooth earbuds discount | promotion_intent | promotion_intent | 1.00 | 1.00 | 1.00 | Budget Bluetooth Earbuds with Charging Case |
| women summer sun protection jacket | scenario_need | scenario_need | 0.80 | 0.60 | 0.80 | Women's Lightweight Sun Protection Jacket |
| oil control sunscreen spf50 | attribute_filter | attribute_filter | 1.00 | 1.00 | 1.00 | Oil Control Sunscreen SPF50 |
| small air fryer for dorm | scenario_need | scenario_need | 1.00 | 1.00 | 1.00 | Compact Air Fryer 3L |
| cordless vacuum for car | attribute_filter | attribute_filter | 1.00 | 1.00 | 1.00 | Cordless Handheld Vacuum Cleaner |
| instant coffee for office | scenario_need | scenario_need | 1.00 | 1.00 | 1.00 | Office Coffee Set |

## Interview Notes

- Keyword/BM25 is the baseline recall path and is strong on exact product terms.
- Semantic expansion improves long-tail and scenario queries, but must be guarded by category and business features.
- Hybrid rerank combines relevance, category match, price/promotion intent, popularity, sales, and rating.
- The current labels are a small offline proxy. A production version should use search logs, clicks, add-to-cart, conversion, and A/B testing.
