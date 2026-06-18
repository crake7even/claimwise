from __future__ import annotations

from dataclasses import dataclass, asdict
import re


TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")
STOPWORDS = {
    "a", "an", "and", "for", "in", "of", "on", "the", "to", "with",
    "的", "了", "和", "给", "适合", "想要", "有", "买",
}

INTENT_RULES = {
    "brand_exact": {
        "terms": {
            "apple", "iphone", "ipad", "samsung", "galaxy", "sony", "lg",
            "canon", "nikon", "hp", "dell", "lenovo", "microsoft", "beats",
            "bose", "小米", "华为", "三星", "苹果",
        },
    },
    "category_browse": {
        "terms": {
            "phone", "phones", "case", "laptop", "camera", "tablet",
            "headphones", "earbuds", "speaker", "tv", "watch", "printer",
            "router", "monitor", "keyboard", "sunscreen", "jacket", "coffee",
            "vacuum", "手机", "手机壳", "耳机", "音箱", "电脑", "键盘",
            "防晒衣", "防晒霜", "咖啡", "吸尘器", "空气炸锅",
        },
    },
    "attribute_filter": {
        "terms": {
            "wireless", "bluetooth", "gaming", "portable", "waterproof",
            "4k", "touchscreen", "prepaid", "refurbished", "clear",
            "transparent", "shockproof", "spf50", "cordless", "mechanical",
            "无线", "蓝牙", "游戏", "便携", "防水", "透明", "防摔",
            "控油", "机械", "无绳",
        },
    },
    "price_sensitive": {
        "terms": {
            "cheap", "budget", "affordable", "low", "discount", "sale",
            "便宜", "低价", "平价", "学生党", "预算", "实惠",
        },
    },
    "promotion_intent": {
        "terms": {"discount", "sale", "coupon", "promo", "deal", "打折", "优惠", "券", "促销"},
    },
    "scenario_need": {
        "terms": {
            "travel", "school", "office", "work", "student", "music",
            "photo", "video", "streaming", "home", "dorm", "cycling",
            "summer", "commute", "旅行", "学校", "办公", "学生", "音乐",
            "拍照", "视频", "家用", "宿舍", "骑车", "夏天", "通勤",
        },
    },
}

SYNONYMS = {
    "cheap": ["budget", "low price", "affordable"],
    "budget": ["cheap", "affordable"],
    "phone": ["cell phone", "smartphone", "mobile"],
    "phones": ["cell phones", "smartphones", "mobile"],
    "case": ["cover", "protective case", "phone case"],
    "headphones": ["headset", "earbuds", "wireless audio"],
    "earbuds": ["headphones", "bluetooth audio"],
    "speaker": ["bluetooth speaker", "audio"],
    "camera": ["photo", "dslr", "digital camera"],
    "tv": ["television", "4k", "streaming"],
    "gaming": ["game", "console", "performance"],
    "school": ["student", "portable", "budget"],
    "travel": ["portable", "battery", "lightweight"],
    "sunscreen": ["spf50", "sun protection", "skincare"],
    "jacket": ["coat", "sun protection", "clothing"],
    "vacuum": ["cleaning", "cordless", "home appliance"],
    "便宜": ["平价", "低价", "budget"],
    "手机": ["phone", "smartphone", "mobile"],
    "手机壳": ["phone case", "cover", "case"],
    "耳机": ["headphones", "earbuds", "bluetooth"],
    "防晒": ["sun protection", "sunscreen", "spf50"],
    "防晒衣": ["sun protection jacket", "summer jacket"],
    "空气炸锅": ["air fryer", "kitchen appliance"],
}

CHINESE_SEGMENT_TERMS = sorted(
    {
        term
        for config in INTENT_RULES.values()
        for term in config["terms"]
        if any("\u4e00" <= char <= "\u9fff" for char in term)
    }
    | {
        term
        for term in SYNONYMS
        if any("\u4e00" <= char <= "\u9fff" for char in term)
    },
    key=len,
    reverse=True,
)

INTENT_PRIORITY = [
    "promotion_intent",
    "price_sensitive",
    "brand_exact",
    "attribute_filter",
    "scenario_need",
    "category_browse",
]


@dataclass(frozen=True)
class QueryIntent:
    query: str
    intent: str
    tokens: list[str]
    expanded_terms: list[str]
    matched_terms: list[str]
    filters: dict
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = TOKEN_RE.findall(lowered)
    for term in CHINESE_SEGMENT_TERMS:
        if term in lowered:
            tokens.append(term)
    return _dedupe([token for token in tokens if token and token not in STOPWORDS])


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        normalized = item.lower()
        if normalized not in seen:
            result.append(item)
            seen.add(normalized)
    return result


def _price_filter(tokens: list[str]) -> dict:
    token_set = set(tokens)
    if token_set & {"cheap", "budget", "affordable", "low", "便宜", "低价", "平价", "学生党", "预算", "实惠"}:
        return {"price_bias": "low"}
    return {}


def analyze_query(query: str) -> QueryIntent:
    tokens = tokenize(query)
    token_set = set(tokens)
    scores: dict[str, int] = {}
    matched_by_intent: dict[str, list[str]] = {}

    for intent, config in INTENT_RULES.items():
        matched = sorted(token_set & config["terms"])
        scores[intent] = len(matched)
        matched_by_intent[intent] = matched

    winner = "broad"
    for intent in INTENT_PRIORITY:
        if scores.get(intent, 0) > 0:
            winner = intent
            break

    expanded_terms = []
    for token in tokens:
        expanded_terms.extend(SYNONYMS.get(token, []))

    matched_terms = matched_by_intent.get(winner, [])
    reason = (
        f"matched {winner}: {', '.join(matched_terms)}"
        if matched_terms
        else "no strong rule hit; use broad product relevance"
    )
    filters = _price_filter(tokens)
    if winner == "promotion_intent":
        filters["promotion"] = True

    return QueryIntent(
        query=query,
        intent=winner,
        tokens=tokens,
        expanded_terms=_dedupe(expanded_terms),
        matched_terms=matched_terms,
        filters=filters,
        reason=reason,
    )


if __name__ == "__main__":
    import argparse
    import json
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()
    print(json.dumps(analyze_query(args.query).to_dict(), ensure_ascii=False, indent=2))
