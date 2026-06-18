from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
from pathlib import Path
import re


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


@dataclass(frozen=True)
class DocChunk:
    id: str
    source: str
    file_name: str
    chunk_id: int
    content: str

    def to_dict(self) -> dict:
        return asdict(self)


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ModuleNotFoundError:
        return ""

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


def chunk_id(source: str, index: int, content: str) -> str:
    digest = hashlib.sha1(f"{source}:{index}:{content}".encode("utf-8")).hexdigest()
    return digest


def load_chunks(docs_dir: Path, chunk_size: int = 1200, overlap: int = 180) -> list[DocChunk]:
    chunks: list[DocChunk] = []
    if not docs_dir.exists():
        return chunks

    for path in sorted(docs_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        text = read_document(path)
        for index, content in enumerate(chunk_text(text, chunk_size=chunk_size, overlap=overlap)):
            source = str(path)
            chunks.append(DocChunk(
                id=chunk_id(source, index, content),
                source=source,
                file_name=path.name,
                chunk_id=index,
                content=content,
            ))
    return chunks
