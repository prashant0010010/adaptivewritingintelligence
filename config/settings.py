"""Application settings. Read from environment / .env. Safe defaults, no secrets in logs."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

GENRES = ["Academic report", "Essay", "Reflective writing", "Professional writing", "Informal", "Other"]


def _default_data_dir() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if local:
        return Path(local) / "AdaptiveWritingIntelligence"
    return Path.home() / ".adaptive_writing_intelligence"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    gemini_api_key: str
    gemini_model: str
    request_timeout: int
    max_retries: int
    max_upload_mb: int
    max_input_chars: int

    @property
    def db_path(self) -> Path:
        return self.data_dir / "awi.db"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.export_dir, self.log_dir, self.backup_dir):
            d.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:  # never reveal the key
        return (f"Settings(data_dir={self.data_dir}, gemini_configured={self.gemini_configured}, "
                f"gemini_model={self.gemini_model})")


def get_settings() -> Settings:
    data_dir = Path(os.getenv("AWI_DATA_DIR") or _default_data_dir())
    return Settings(
        data_dir=data_dir,
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        request_timeout=_int("AWI_REQUEST_TIMEOUT", 60),
        max_retries=_int("AWI_MAX_RETRIES", 2),
        max_upload_mb=_int("AWI_MAX_UPLOAD_MB", 5),
        max_input_chars=_int("AWI_MAX_INPUT_CHARS", 60000),
    )
