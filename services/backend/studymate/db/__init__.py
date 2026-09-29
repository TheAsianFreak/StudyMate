"""SQLite access for learning data (documents, chunks, quiz items, wrong notes, review cards).

Owned by the data area. Other areas use the functions in `studymate.learning.store`
and `studymate.rag.retrieve` instead of touching tables directly.

Concurrency: the process shares one connection (WAL mode) guarded by a re-entrant lock.
Handlers run DB work through `asyncio.to_thread`, so every statement executes in a worker
thread; all statements here are short (the slow parts, PDF extraction and embedding,
happen outside the lock).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import sqlite_vec

if TYPE_CHECKING:
    from studymate.services import Services

log = logging.getLogger(__name__)

EMBED_DIM = 1024  # bge-m3; changing the embedding model needs a new migration

# Append-only: never edit an applied migration, add a new one instead.
MIGRATIONS: list[str] = [
    # 1: initial schema
    f"""
    CREATE TABLE documents (
        doc_id       TEXT PRIMARY KEY,
        title        TEXT NOT NULL,
        path         TEXT NOT NULL,
        sha256       TEXT NOT NULL UNIQUE,
        pages        INTEGER NOT NULL,
        chunks       INTEGER NOT NULL,
        empty_pages  TEXT NOT NULL DEFAULT '[]',  -- JSON list of 1-based pages without a text layer
        imported_at  TEXT NOT NULL
    );

    CREATE TABLE chunks (
        chunk_id  INTEGER PRIMARY KEY,
        doc_id    TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
        page      INTEGER NOT NULL,  -- 1-based
        ord       INTEGER NOT NULL,  -- order within the document
        text      TEXT NOT NULL
    );
    CREATE INDEX chunks_doc ON chunks(doc_id, ord);

    CREATE VIRTUAL TABLE chunk_vecs USING vec0(
        chunk_id  INTEGER PRIMARY KEY,
        doc_id    TEXT PARTITION KEY,
        embedding FLOAT[{EMBED_DIM}] distance_metric=cosine
    );
    CREATE TRIGGER chunks_after_delete AFTER DELETE ON chunks BEGIN
        DELETE FROM chunk_vecs WHERE chunk_id = old.chunk_id;
    END;

    CREATE TABLE quiz_items (
        item_id     TEXT PRIMARY KEY,
        item        TEXT NOT NULL,  -- QuizItem JSON
        created_at  TEXT NOT NULL
    );

    CREATE TABLE attempts (
        attempt_id  INTEGER PRIMARY KEY,
        item_id     TEXT NOT NULL REFERENCES quiz_items(item_id) ON DELETE CASCADE,
        answer      TEXT NOT NULL,
        correct     INTEGER NOT NULL,
        at          TEXT NOT NULL
    );
    CREATE INDEX attempts_item ON attempts(item_id, at);

    CREATE TABLE wrong_notes (
        note_id      TEXT PRIMARY KEY,
        item_id      TEXT NOT NULL UNIQUE REFERENCES quiz_items(item_id) ON DELETE CASCADE,
        user_answer  TEXT NOT NULL,
        created_at   TEXT NOT NULL
    );

    CREATE TABLE review_cards (
        card_id     TEXT PRIMARY KEY,
        note_id     TEXT NOT NULL UNIQUE REFERENCES wrong_notes(note_id) ON DELETE CASCADE,
        item_id     TEXT NOT NULL REFERENCES quiz_items(item_id) ON DELETE CASCADE,
        fsrs        TEXT NOT NULL,  -- py-fsrs Card JSON
        due         TEXT NOT NULL,  -- ISO 8601 UTC, fixed width so text order = time order
        state       TEXT NOT NULL,  -- learning | review | relearning
        reps        INTEGER NOT NULL DEFAULT 0,
        lapses      INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL
    );
    CREATE INDEX review_cards_due ON review_cards(due);

    CREATE TABLE review_logs (
        log_id       INTEGER PRIMARY KEY,
        card_id      TEXT NOT NULL REFERENCES review_cards(card_id) ON DELETE CASCADE,
        rating       INTEGER NOT NULL,
        reviewed_at  TEXT NOT NULL
    );
    CREATE INDEX review_logs_card ON review_logs(card_id);
    """,
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    """ISO 8601 UTC with millisecond precision and a `Z` suffix (fixed width, sortable)."""
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def connect(path: Path) -> sqlite3.Connection:
    """Opens the database with sqlite-vec loaded and migrations applied.

    The connection is in autocommit mode (`isolation_level=None`); group writes with
    explicit transactions (see `Database.write`).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0, isolation_level=None, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        _migrate(conn)
    except BaseException:
        conn.close()
        raise
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
    if current > len(MIGRATIONS):
        raise RuntimeError(f"database schema v{current} is newer than this build (v{len(MIGRATIONS)})")
    for version in range(current + 1, len(MIGRATIONS) + 1):
        log.info("applying db migration %d", version)
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _split_sql(MIGRATIONS[version - 1]):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)", (version, iso(utc_now()))
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise


def _split_sql(script: str) -> list[str]:
    """Splits a migration into statements (executescript would commit our transaction)."""
    statements: list[str] = []
    buf = ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                statements.append(buf.strip())
            buf = ""
    if buf.strip():
        statements.append(buf.strip())
    return statements


class Database:
    """Process-wide connection guarded by a lock; reconnects after `close()`."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        with self._lock:
            self._conn = connect(path)

    def _ensure(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = connect(self.path)
        return self._conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._ensure()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """One transaction: committed on success, rolled back on any exception."""
        with self._lock:
            conn = self._ensure()
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


def get_db(services: Services) -> Database:
    """The shared database at `settings.db_path`, opened on first use."""

    def factory() -> Database:
        db = Database(services.settings.db_path)
        services.cleanups.append(db.close)
        return db

    return services.lazy("db", factory)
