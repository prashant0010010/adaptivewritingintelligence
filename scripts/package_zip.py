"""Create a clean ZIP of the project (no .env, databases, caches or virtual environments).
Usage: python scripts/package_zip.py"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".git", "dist", "exports", "backups", "logs"}
SKIP_SUFFIX = {".pyc", ".db", ".sqlite", ".sqlite3", ".log", ".zip"}
out = ROOT.parent / f"{ROOT.name}.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if p.is_dir() or SKIP_DIRS & set(rel.parts) or p.suffix in SKIP_SUFFIX or p.name == ".env":
            continue
        z.write(p, Path(ROOT.name) / rel)
print("Wrote", out)
