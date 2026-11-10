"""Almacenamiento SQLite de patrones e imagenes con vencimiento."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PatternRecord:
    id: str
    pattern: dict[str, Any]
    text_es: str
    text_en: str
    created_at: str


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS patterns (
                    id TEXT PRIMARY KEY,
                    pattern_json TEXT NOT NULL,
                    text_es TEXT NOT NULL,
                    text_en TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS images (
                    id TEXT PRIMARY KEY,
                    data BLOB NOT NULL,
                    mime_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                """
            )

    def save_pattern(
        self,
        pattern: dict[str, Any],
        text_es: str,
        text_en: str,
        *,
        created_at: str,
    ) -> str:
        pattern_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO patterns (id, pattern_json, text_es, text_en, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    pattern_id,
                    json.dumps(pattern, ensure_ascii=False),
                    text_es,
                    text_en,
                    created_at,
                ),
            )
        return pattern_id

    def get_pattern(self, pattern_id: str) -> PatternRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, pattern_json, text_es, text_en, created_at"
                " FROM patterns WHERE id = ?",
                (pattern_id,),
            ).fetchone()
        if row is None:
            return None
        return PatternRecord(
            id=row["id"],
            pattern=json.loads(row["pattern_json"]),
            text_es=row["text_es"],
            text_en=row["text_en"],
            created_at=row["created_at"],
        )

    def save_image(self, data: bytes, mime_type: str, *, ttl_hours: float) -> str:
        image_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO images (id, data, mime_type, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    image_id,
                    data,
                    mime_type,
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                    now + ttl_hours * 3600,
                ),
            )
        return image_id

    def get_image(self, image_id: str) -> tuple[bytes, str] | None:
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT data, mime_type FROM images WHERE id = ? AND expires_at > ?",
                (image_id, now),
            ).fetchone()
        if row is None:
            return None
        return bytes(row["data"]), str(row["mime_type"])

    def purge_expired_images(self) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM images WHERE expires_at <= ?", (now,)
            )
            return int(cursor.rowcount)


def database_from_env(env: dict[str, str] | None = None) -> Database:
    values = os.environ if env is None else env
    path = Path(values.get("DATABASE_PATH") or "data/tejedora.sqlite3")
    return Database(path)
