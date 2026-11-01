"""Durable records for containers whose cleanup needs reconciliation."""

import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.execute("CREATE TABLE IF NOT EXISTS containers (name TEXT PRIMARY KEY, token TEXT NOT NULL, created_at REAL NOT NULL)")
    return connection


def journal_path() -> Path:
    return Path(os.environ.get("MERCHANT_SANDBOX_JOURNAL", "runs/python_sandbox.sqlite3"))


def record(name: str, token: str) -> None:
    with closing(_connect(journal_path())) as db, db:
        db.execute("INSERT INTO containers VALUES (?, ?, ?)", (name, token, time.time()))


def forget(name: str, token: str) -> None:
    with closing(_connect(journal_path())) as db, db:
        db.execute("DELETE FROM containers WHERE name = ? AND token = ?", (name, token))


def pending() -> list[tuple[str, str, float]]:
    with closing(_connect(journal_path())) as db:
        return db.execute("SELECT name, token, created_at FROM containers ORDER BY created_at").fetchall()
