"""校验评测集：字段完整、ID 唯一，且每个定位关键词能在依据文件的某个 chunk 中找到。

用法：python eval/validate_dataset.py [eval/dataset.jsonl]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from rag_upgrade.config import DOCS_DIR, env_int  # noqa: E402
from rag_upgrade.document_loader import load_chunks  # noqa: E402

CATEGORIES = {"fact", "paraphrase", "compare", "procedure", "out_of_scope"}
REQUIRED = {"id", "question", "category", "expected_sources", "key_points", "should_refuse", "split"}


def normalize(text: str) -> str:
    """去掉所有空白，避免 PDF 抽取时的硬换行影响关键词匹配。"""
    return re.sub(r"\s+", "", text)


def validate(path: Path) -> list[str]:
    chunks = load_chunks(
        DOCS_DIR,
        chunk_size=env_int("RAG_CHUNK_SIZE", 1200),
        overlap=env_int("RAG_CHUNK_OVERLAP", 180),
    )
    chunks_by_stem: dict[str, list[str]] = {}
    for chunk in chunks:
        chunks_by_stem.setdefault(Path(chunk.file_name).stem, []).append(normalize(chunk.content))

    errors: list[str] = []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = Counter(row.get("id") for row in rows)
    errors.extend(f"重复 ID: {item}" for item, count in ids.items() if count > 1)

    for row in rows:
        rid = row.get("id", "?")
        missing = REQUIRED - row.keys()
        if missing:
            errors.append(f"{rid}: 缺少字段 {sorted(missing)}")
            continue
        if row["category"] not in CATEGORIES:
            errors.append(f"{rid}: 未知 category {row['category']}")
        if row["category"] != "out_of_scope" and not row["expected_sources"]:
            errors.append(f"{rid}: 非库外题必须有 expected_sources")
        if not row["key_points"]:
            errors.append(f"{rid}: key_points 为空")
        for source in row["expected_sources"]:
            texts = chunks_by_stem.get(source["file"])
            if texts is None:
                errors.append(f"{rid}: 文件未加载 {source['file']}")
                continue
            for keyword in source["keywords"]:
                if not any(normalize(keyword) in text for text in texts):
                    errors.append(f"{rid}: 关键词 '{keyword}' 不在 {source['file']} 的任何 chunk 中")

    print(f"{len(rows)} 条，分布 {dict(Counter(row.get('category') for row in rows))}，"
          f"split {dict(Counter(row.get('split') for row in rows))}")
    return errors


if __name__ == "__main__":
    dataset = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND_DIR / "eval" / "dataset.jsonl"
    problems = validate(dataset)
    for problem in problems:
        print("ERROR", problem)
    print("OK" if not problems else f"{len(problems)} 个问题")
    sys.exit(1 if problems else 0)
