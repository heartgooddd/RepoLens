"""Bounded, text-only snapshots. Names are checked before exclusion or disk writes."""

import re
from pathlib import PurePosixPath

from fastapi import HTTPException

MAX_FILE = 1024 * 1024
MAX_TOTAL = 8 * 1024 * 1024
MAX_FILES = 500
MAX_BODY = 12 * 1024 * 1024
EXCLUDED_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "dist", "build", ".next", "__pycache__", ".pytest_cache", "coverage", ".ssh", ".aws", "var"}
EXCLUDED_NAMES = {".ds_store", ".npmrc", ".pypirc", "credentials", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".sql", ".sh", ".gitignore", ".lock", ".csv"}


def fail(code: str, message: str, status: int = 422):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def validate_path(path: str) -> str:
    parts = path.split("/")
    if (not path or len(path.encode("utf-8")) > 700 or len(parts) > 20
            or any(p in ("", ".", "..") or len(p.encode("utf-8")) > 200 for p in parts)
            or re.search(r'[\\:<>"|?*\x00-\x1f\x7f]', path)
            or any(p.endswith((" ", ".")) for p in parts)):
        fail("invalid_path", "文件路径非法：需要无 ..、绝对路径或特殊控制字符的相对路径。")
    return path


def excluded(path: str) -> bool:
    parts = path.lower().split("/")
    name = parts[-1]
    return (any(part in EXCLUDED_DIRS for part in parts[:-1])
            or name in EXCLUDED_NAMES or name.startswith(".env")
            or name.endswith((".pem", ".key", ".p12", ".pfx", ".sqlite3", ".db"))
            or "secret" in name or "credential" in name)


def supported(path: str) -> bool:
    file = PurePosixPath(path.lower())
    return file.suffix in TEXT_SUFFIXES or file.name in {"license", "readme", "dockerfile", "makefile", ".gitignore"}
