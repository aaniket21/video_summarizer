import json
import os
from pathlib import Path
from typing import Any, Dict


_cached_file_path: str | None = None
_cached_file_secrets: Dict[str, Any] | None = None


def _load_file_secrets() -> Dict[str, Any]:
    global _cached_file_path, _cached_file_secrets

    secrets_path = os.getenv("SECRETS_FILE", "")
    if not secrets_path:
        return {}

    if _cached_file_path == secrets_path and _cached_file_secrets is not None:
        return _cached_file_secrets

    try:
        contents = Path(secrets_path).read_text(encoding="utf-8")
        payload = json.loads(contents)
    except Exception:
        payload = {}

    _cached_file_path = secrets_path
    _cached_file_secrets = payload if isinstance(payload, dict) else {}
    return _cached_file_secrets


def get_secret(name: str, default: str = "") -> str:
    provider = os.getenv("SECRETS_PROVIDER", "env").strip().lower()
    if provider == "file":
        value = _load_file_secrets().get(name, default)
        return str(value) if value is not None else ""

    value = os.getenv(name, default)
    return str(value) if value is not None else ""
