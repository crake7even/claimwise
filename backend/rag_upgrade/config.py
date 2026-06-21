from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
EMBEDDING_CACHE = WORKSPACE_DIR / "embedding_cache.json"


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def es_base_url() -> str:
    raw_host = os.getenv("ES_HOST")
    host = (raw_host or "https://localhost").rstrip("/")
    default_port = "9200" if raw_host is None or "localhost" in host or "127.0.0.1" in host else ""
    port = os.getenv("ES_PORT", default_port).strip()
    if port and ":" not in host.rsplit("/", 1)[-1]:
        return f"{host}:{port}"
    return host
