from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import logging
from pathlib import Path
import re


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}
# 抽取文本少于该字数的文档视为加载失败（如扫描件 PDF），不进入语料
MIN_DOC_CHARS = 50

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocChunk:
    id: str
    source: str
    file_name: str
    chunk_id: int
    content: str
    section: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


class PdfSupportMissing(RuntimeError):
    pass


def read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ModuleNotFoundError as exc:
        raise PdfSupportMissing("pdfplumber is not installed") from exc

    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf(path)
    return read_text_file(path)


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


# 结构化切分：按问答块（Q1）、条款（第X条）、释义词条（【火车】）和中文序号小节（一、）切分，
# 章节标题（如"责任免除"）作为上下文前缀写入 chunk，便于检索时区分同文档内相似段落。
SECTION_START_RE = re.compile(r"^(Q\s*\d+|第[一二三四五六七八九十百零]+条|【[^】]{1,20}】|[一二三四五六七八九十]+、|给付表)")
ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百零]+条")
# 产品说明类条款用"五、责任免除"作章节标题
NUMBERED_CHAPTER_RE = re.compile(r"^[一二三四五六七八九十]+、[^，。；：]{2,10}$")
MIN_SECTION_CHARS = 80
PUNCTUATION_RE = re.compile(r"[，。；：、,.;:（）()\d%“”]")


def doc_title(path: Path) -> str:
    return re.sub(r"^\d+-", "", path.stem)


def _is_chapter_heading(line: str) -> bool:
    return 2 <= len(line) <= 10 and not PUNCTUATION_RE.search(line) and not SECTION_START_RE.match(line)


def split_sections(text: str) -> list[tuple[str, str]]:
    """切成 (小节标签, 正文) 列表；只有条款类文档（含"第X条"）才识别章节标题。"""
    lines = clean_text(text).split("\n")
    is_clause_doc = any(ARTICLE_RE.match(line.strip()) for line in lines)
    sections: list[tuple[str, list[str]]] = []
    chapter = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if is_clause_doc and (_is_chapter_heading(line) or NUMBERED_CHAPTER_RE.match(line)):
            chapter = line.replace(" ", "")
            sections.append((chapter, []))
            continue
        match = SECTION_START_RE.match(line)
        if match:
            heading = line[:24] if line.startswith("Q") else match.group(1)
            label = f"{chapter} {heading}".strip() if is_clause_doc else heading
            sections.append((label, [line]))
            continue
        if not sections:
            sections.append((chapter, []))
        sections[-1][1].append(line)
    return [(label, "\n".join(body)) for label, body in sections if body]


def chunk_structured(text: str, title: str, max_chars: int = 600, overlap: int = 80) -> list[tuple[str, str]]:
    """合并同章节的短小节、拆分超长小节，返回 (section, content)；content 带文档名与小节前缀。"""
    merged: list[tuple[str, str]] = []
    pending = ""  # 过短的标题/导语并入下一个小节，避免产生只有标题的 chunk
    for label, body in split_sections(text):
        if pending:
            body, pending = pending + "\n" + body, ""
        if len(body) < MIN_SECTION_CHARS:
            pending = body
            continue
        chapter = label.split(" ")[0] if " " in label else ""
        if merged:
            prev_label, prev_body = merged[-1]
            prev_chapter = prev_label.split(" ")[0] if " " in prev_label else ""
            if chapter and chapter == prev_chapter and len(prev_body) + len(body) + 1 <= max_chars:
                merged[-1] = (f"{prev_label}、{label.split(' ', 1)[-1]}", prev_body + "\n" + body)
                continue
        merged.append((label, body))
    if pending:
        if merged:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n" + pending)
        else:
            merged.append(("", pending))

    results: list[tuple[str, str]] = []
    for label, body in merged:
        pieces = [body] if len(body) <= max_chars else chunk_text(body, chunk_size=max_chars, overlap=overlap)
        for piece in pieces:
            prefix = f"《{title}》{label}".strip()
            results.append((label, f"{prefix}\n{piece}"))
    return results


def chunk_id(source: str, index: int, content: str) -> str:
    digest = hashlib.sha1(f"{source}:{index}:{content}".encode("utf-8")).hexdigest()
    return digest


def load_chunks(docs_dir: Path, chunk_size: int = 1200, overlap: int = 180, strategy: str = "structured") -> list[DocChunk]:
    return load_corpus(docs_dir, chunk_size=chunk_size, overlap=overlap, strategy=strategy)[0]


def load_corpus(
    docs_dir: Path, chunk_size: int = 1200, overlap: int = 180, strategy: str = "structured",
) -> tuple[list[DocChunk], list[dict]]:
    """加载语料，同时返回每份文档的加载报告；抽取失败或过短的文档会被跳过并记录 warning。"""
    chunks: list[DocChunk] = []
    report: list[dict] = []
    if not docs_dir.exists():
        logger.warning("docs dir not found: %s", docs_dir)
        return chunks, report

    for path in sorted(docs_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            text = clean_text(read_document(path))
        except PdfSupportMissing as exc:
            logger.warning("skip %s: %s", path.name, exc)
            report.append({"file": path.name, "chars": 0, "chunks": 0, "status": f"skipped: {exc}"})
            continue
        except Exception as exc:
            logger.warning("skip %s: read failed: %s", path.name, exc)
            report.append({"file": path.name, "chars": 0, "chunks": 0, "status": f"skipped: read failed: {type(exc).__name__}"})
            continue
        if len(text) < MIN_DOC_CHARS:
            logger.warning("skip %s: extracted only %d chars (scanned PDF?)", path.name, len(text))
            report.append({"file": path.name, "chars": len(text), "chunks": 0, "status": f"skipped: text too short (<{MIN_DOC_CHARS} chars)"})
            continue
        start_count = len(chunks)
        if strategy == "fixed":
            pieces = [("", content) for content in chunk_text(text, chunk_size=chunk_size, overlap=overlap)]
        else:
            pieces = chunk_structured(text, doc_title(path), max_chars=chunk_size, overlap=overlap)
        for index, (section, content) in enumerate(pieces):
            source = str(path)
            chunks.append(DocChunk(
                id=chunk_id(source, index, content),
                source=source,
                file_name=path.name,
                chunk_id=index,
                content=content,
                section=section,
            ))
        report.append({"file": path.name, "chars": len(text), "chunks": len(chunks) - start_count, "status": "loaded"})
    return chunks, report
