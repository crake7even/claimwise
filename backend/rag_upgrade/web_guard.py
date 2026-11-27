"""联网搜索防护：主题闸门（只为保险相关问题联网）、搜索词收紧、网页内容消毒。"""
from __future__ import annotations

import re

# 命中任一词即视为保险相关，可直接联网（与查询改写并行）；未命中时由改写器判定
INSURANCE_KEYWORDS = (
    "保险", "险", "赔", "保费", "保额", "保单", "投保", "承保", "核保", "退保", "续保", "保障",
    "被保", "受益人", "等待期", "免责", "责任免除", "条款", "精算", "偿付能力", "监管总局", "银保监",
    "平安", "人保", "太保", "国寿", "众安",
)
# 改写器对与保险完全无关的问题输出该标记（见 query_rewriter.REWRITE_PROMPT）
OFF_TOPIC_MARK = "无关"
WEB_QUERY_MAX_CHARS = 60

# 网页摘要中伪造的资料分隔标签、对话角色标签和其他 HTML 标签，避免跳出 <联网资料> 隔离区
_TAG_RE = re.compile(r"<\s*/?\s*(?:联网资料|资料|system|assistant|user|[a-zA-Z][\w-]{0,20})\b[^<>]{0,200}>", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def is_insurance_related(text: str | None) -> bool:
    return bool(text) and any(word in text for word in INSURANCE_KEYWORDS)


def is_off_topic_verdict(rewritten: str | None) -> bool:
    return bool(rewritten) and rewritten.strip().strip("。.") == OFF_TOPIC_MARK


def clamp_query(query: str) -> str:
    """发给搜索服务的查询：合并空白并按 Unicode 字符截断，避免把整段长文本当搜索词。"""
    text = _WHITESPACE_RE.sub(" ", query or "").strip()
    return "".join(list(text)[:WEB_QUERY_MAX_CHARS])


def sanitize_web_text(text: str) -> str:
    return _TAG_RE.sub("", text or "")
