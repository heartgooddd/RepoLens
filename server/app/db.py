"""Short-lived SQLite connections; ordered, transactional, checksum-checked migrations."""

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


@contextmanager
def connect(database: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def migrate(database: Path, directory: Path = MIGRATIONS) -> int:
    files = sorted(directory.glob("*.sql"))
    if not files:
        raise RuntimeError("No database migrations found")
    versions: list[tuple[int, Path]] = []
    for file in files:
        match = re.fullmatch(r"(\d{3})_[a-z0-9_]+\.sql", file.name)
        if not match:
            raise RuntimeError(f"Invalid migration filename: {file.name}")
        versions.append((int(match[1]), file))
    if [v for v, _ in versions] != list(range(1, len(versions) + 1)):
        raise RuntimeError("Migrations must have consecutive versions starting at 001")
    with connect(database) as connection:
        # One lock/transaction covers validation, DDL, and history, including concurrent starts.
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )""")
            applied = {r["version"]: r for r in connection.execute("SELECT * FROM schema_migrations")}
            if sorted(applied) != list(range(1, len(applied) + 1)) or len(applied) > len(versions):
                raise RuntimeError("Database migration history is incompatible with this code")
            for version, file in versions:
                raw = file.read_bytes()
                checksum = hashlib.sha256(raw).hexdigest()
                if version in applied:
                    if applied[version]["checksum"] != checksum or applied[version]["name"] != file.name:
                        raise RuntimeError(f"Applied migration was modified: {file.name}")
                    continue
                # executescript implicitly commits; execute complete SQL statements instead.
                statement = ""
                for line in raw.decode("utf-8").splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        connection.execute(statement)
                        statement = ""
                if statement.strip():
                    raise RuntimeError(f"Incomplete SQL statement: {file.name}")
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, checksum) VALUES (?, ?, ?)",
                    (version, file.name, checksum),
                )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return len(versions)
