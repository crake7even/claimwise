from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import statistics
from typing import Iterable

from .config import DATA_DIR, EXTERNAL_ECOMMERCE_PATH


@dataclass
class Product:
    id: str
    name: str
    description: str
    brand: str
    categories: list[str]
    price: float
    image: str
    popularity: float
    sales: float
    rating: float
    tags: list[str]
    promotion: bool
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable_rating(item: dict, index: int) -> float:
    if "rating" in item and item["rating"] is not None:
        return float(item["rating"])
    base = 4.0 + ((int(item.get("popularity", 0)) + index) % 10) / 10
    return round(min(base, 4.9), 1)


def _stable_sales(item: dict, index: int) -> float:
    if "sales" in item and item["sales"] is not None:
        return float(item["sales"])
    return float(max(10, int(item.get("popularity", 0)) // 4 + index % 97))


def _infer_tags(item: dict) -> list[str]:
    text = " ".join([
        item.get("name", ""),
        item.get("description", ""),
        item.get("brand", ""),
        " ".join(item.get("categories", [])),
    ]).lower()
    candidates = [
        "iphone", "samsung", "case", "wireless", "bluetooth", "gaming",
        "portable", "waterproof", "4k", "prepaid", "refurbished", "camera",
        "laptop", "tablet", "speaker", "headphones", "printer", "office",
        "student", "travel", "cheap", "budget", "phone", "sunscreen",
        "jacket", "coffee", "air fryer", "vacuum",
    ]
    return [tag for tag in candidates if tag in text]


def _search_text(item: dict) -> str:
    return " ".join([
        str(item.get("name", "")),
        str(item.get("description", "")),
        str(item.get("brand", "")),
        " ".join(str(x) for x in item.get("categories", [])),
        " ".join(str(x) for x in item.get("tags", [])),
    ]).lower()


def _image_match_terms(item: dict) -> list[str]:
    text = _search_text(item)
    priority_terms = [
        "iphone", "ipad", "macbook", "apple watch", "airpods", "apple",
        "samsung", "galaxy", "case", "headphones", "earbuds", "speaker",
        "bluetooth", "laptop", "keyboard", "tv", "camera", "printer",
        "tablet", "phone", "sunscreen", "jacket", "coffee", "air fryer",
        "vacuum",
    ]
    terms = [term for term in priority_terms if term in text]
    terms.extend(str(x).lower() for x in item.get("tags", []))
    for category in item.get("categories", []):
        terms.extend(str(category).lower().split())
    return list(dict.fromkeys(term for term in terms if len(term) > 2))


def _build_image_candidates(external_items: list[dict]) -> list[dict]:
    candidates = []
    for item in external_items:
        image = str(item.get("image", "")).strip()
        if not image:
            continue
        name = str(item.get("name", "")).lower()
        categories = " ".join(str(x) for x in item.get("categories", [])).lower()
        description = str(item.get("description", "")).lower()
        candidates.append({
            "image": image,
            "text": _search_text(item),
            "name": name,
            "categories": categories,
            "description": description,
        })
    return candidates


def _match_local_image(item: dict, image_candidates: list[dict]) -> str:
    if str(item.get("image", "")).strip():
        return str(item["image"]).strip()
    terms = _image_match_terms(item)
    if not terms:
        return ""

    best_score = 0
    best_image = ""
    item_category_text = " ".join(str(x) for x in item.get("categories", [])).lower()
    audio_like = any(term in item_category_text for term in ["audio", "headphone", "earbud", "speaker"])
    case_like = any(term in item_category_text for term in ["case", "accessor"])
    for candidate in image_candidates:
        score = 0
        candidate_category = candidate["categories"]
        if audio_like and any(term in candidate_category for term in ["headset", "headphone", "audio"]):
            score += 12
        if case_like and any(term in candidate_category for term in ["case", "clip", "accessor"]):
            score += 10
        for term in terms:
            if term in candidate["name"]:
                score += 8 if term in {"iphone", "apple", "samsung", "case", "headphones", "speaker", "bluetooth"} else 4
            if term in candidate_category:
                score += 6
            if term in candidate["description"]:
                score += 1
        if score > best_score:
            best_score = score
            best_image = candidate["image"]
    return best_image if best_score > 0 else ""


def _normalize(item: dict, index: int, source: str, image_candidates: list[dict] | None = None) -> Product:
    categories = [str(x) for x in item.get("categories", []) if str(x).strip()]
    price = float(item.get("price") or 0.0)
    popularity = float(item.get("popularity") or item.get("sales") or 0.0)
    tags = item.get("tags") or _infer_tags(item)
    promotion = bool(item.get("promotion", price <= 20 or index % 11 == 0))
    image = _match_local_image({**item, "tags": tags, "categories": categories}, image_candidates or [])
    return Product(
        id=str(item.get("id") or f"{source}-{index:05d}"),
        name=str(item.get("name", "")).strip(),
        description=str(item.get("description", "")).strip(),
        brand=str(item.get("brand", "Unknown")).strip() or "Unknown",
        categories=categories or ["Uncategorized"],
        price=price,
        image=image,
        popularity=popularity,
        sales=_stable_sales(item, index),
        rating=_stable_rating(item, index),
        tags=[str(tag).lower() for tag in tags],
        promotion=promotion,
        source=source,
    )


def _generated_catalog() -> list[dict]:
    categories = [
        ("Fashion", "Women's Clothing", "Dresses", ["summer", "women", "dress", "commute"]),
        ("Fashion", "Men's Clothing", "Shirts", ["men", "shirt", "office", "quick dry"]),
        ("Beauty", "Skincare", "Sunscreen", ["sunscreen", "spf50", "oil control", "summer"]),
        ("Beauty", "Makeup", "Lip Makeup", ["lip tint", "makeup", "hydrating", "daily"]),
        ("Home Appliances", "Kitchen Appliances", "Air Fryers", ["air fryer", "kitchen", "compact", "dorm"]),
        ("Home Appliances", "Cleaning Appliances", "Vacuum Cleaners", ["vacuum", "cordless", "portable", "car"]),
        ("Home", "Storage", "Desk Organizers", ["home", "office", "storage", "desk"]),
        ("Groceries", "Beverages", "Coffee", ["coffee", "instant", "office", "breakfast"]),
        ("Groceries", "Instant Food", "Noodles", ["ramen", "noodles", "spicy", "snack"]),
        ("Toys", "Learning Toys", "Drawing Tablets", ["kids", "learning", "drawing", "tablet"]),
    ]
    adjectives = ["Budget", "Premium", "Portable", "Lightweight", "Daily", "Compact", "Summer", "Office"]
    generated = []
    for cat_index, (level1, level2, level3, tags) in enumerate(categories):
        for variant_index, adjective in enumerate(adjectives):
            price = 5.9 + cat_index * 7 + variant_index * 3.4
            generated.append({
                "id": f"generated-{cat_index:02d}-{variant_index:02d}",
                "name": f"{adjective} {level3[:-1] if level3.endswith('s') else level3} Set",
                "description": (
                    f"{adjective.lower()} {level3.lower()} product for {level2.lower()} "
                    f"with {' '.join(tags[:3])} features."
                ),
                "brand": ["Shopee Choice", "DailyMall", "ValueHub", "UrbanGo"][variant_index % 4],
                "categories": [level1, level2, level3],
                "price": round(price, 2),
                "image": "",
                "popularity": 4000 + cat_index * 900 + variant_index * 137,
                "sales": 600 + cat_index * 320 + variant_index * 81,
                "rating": round(4.1 + (variant_index % 5) * 0.15, 1),
                "tags": tags + [adjective.lower()],
                "promotion": variant_index in {0, 4, 6},
            })
    return generated


def load_products(limit_external: int | None = 600) -> list[dict]:
    products: list[Product] = []
    external_all = _read_json(EXTERNAL_ECOMMERCE_PATH) if EXTERNAL_ECOMMERCE_PATH.exists() else []
    image_candidates = _build_image_candidates(external_all)

    seed_path = DATA_DIR / "seed_products.json"
    for index, item in enumerate(_read_json(seed_path)):
        products.append(_normalize(item, index, "seed", image_candidates))

    offset = len(products)
    for index, item in enumerate(_generated_catalog(), start=offset):
        products.append(_normalize(item, index, "generated_seed", image_candidates))

    if external_all:
        external = external_all
        if limit_external:
            external = external[:limit_external]
        offset = len(products)
        for index, item in enumerate(external, start=offset):
            products.append(_normalize(item, index, "external_3c", image_candidates))

    return [product.to_dict() for product in products if product.name and product.description]


def category_distribution(products: Iterable[dict], level: int = 0) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for product in products:
        categories = product.get("categories", [])
        category = categories[level] if len(categories) > level else "<missing>"
        counts[category] = counts.get(category, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def dataset_profile(products: list[dict]) -> dict:
    prices = [float(product["price"]) for product in products]
    missing = {}
    for field in ["name", "description", "brand", "categories", "price", "popularity", "sales", "rating", "image"]:
        missing[field] = sum(1 for product in products if not product.get(field))
    return {
        "count": len(products),
        "sources": category_distribution([{"categories": [p["source"]]} for p in products]),
        "top_level_categories": category_distribution(products, 0)[:10],
        "second_level_categories": category_distribution(products, 1)[:12],
        "price": {
            "min": round(min(prices), 2),
            "max": round(max(prices), 2),
            "avg": round(statistics.mean(prices), 2),
            "median": round(statistics.median(prices), 2),
        },
        "missing": missing,
    }


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    loaded = load_products()
    print(json.dumps(dataset_profile(loaded), ensure_ascii=False, indent=2))
