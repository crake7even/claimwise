from __future__ import annotations

from .data_loader import load_products, dataset_profile
from .query_intent import analyze_query
from .search_service import CommerceSearchService


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    products = load_products()
    profile = dataset_profile(products)
    assert_true(profile["count"] >= 500, "dataset should include local external data plus seed data")
    assert_true(len(profile["top_level_categories"]) >= 6, "dataset should cover multiple ecommerce categories")
    assert_true(all(value == 0 for value in profile["missing"].values()), "core product fields should be complete")

    chinese_intent = analyze_query("便宜的蓝牙耳机")
    assert_true(chinese_intent.intent == "price_sensitive", "Chinese low-price query should be price_sensitive")
    assert_true("耳机" in chinese_intent.tokens and "蓝牙" in chinese_intent.tokens, "Chinese ecommerce terms should be segmented")

    service = CommerceSearchService(products)
    cases = {
        "iPhone 15 clear case": "case",
        "cheap laptop for school": "laptop",
        "oil control sunscreen spf50": "sunscreen",
        "small air fryer for dorm": "air fryer",
        "便宜的蓝牙耳机": "earbuds",
    }
    for query, expected in cases.items():
        output = service.search(query, top_k=5)
        names = " ".join(item["name"].lower() for item in output["results"])
        assert_true(expected in names, f"{query!r} should retrieve a result containing {expected!r}")

    iphone_results = service.search("iPhone", top_k=5)["results"]
    assert_true(any(item["image"] for item in iphone_results), "iPhone recommendations should include local product images")

    audio_results = service.search("便宜的蓝牙耳机", top_k=5)["results"]
    assert_true(any(item["image"] for item in audio_results), "bluetooth earbud recommendations should include local product images")

    print("commerce_search smoke test passed")


if __name__ == "__main__":
    main()
