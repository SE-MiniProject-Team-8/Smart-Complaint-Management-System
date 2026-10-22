"""SQLite connection handling and the shared transaction boundary (C09)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .errors import AppError, persistence_unavailable

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
BUSY_TIMEOUT_SECONDS = 5


def utc_now():
    """UTC ISO 8601 timestamp (second precision, trailing Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(database_path):
    """Open a connection with foreign keys on and explicit transaction control."""
    conn = sqlite3.connect(str(database_path), timeout=BUSY_TIMEOUT_SECONDS,
                           isolation_level=None)  # we issue BEGIN/COMMIT ourselves
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_SECONDS * 1000}")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -2000")
    if str(database_path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")  # durable commits
    return conn


def init_db(database_path):
    """Create tables, indexes and triggers if they do not exist (idempotent)."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(database_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()


@contextmanager
def transaction(conn):
    """One atomic unit of work.

    Complaint state, assignment history, audit and notification rows are all
    written inside a single transaction, so a complaint can never be committed
    without its accountability records. Any failure rolls everything back.
    """
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        raise persistence_unavailable() from exc
    try:
        yield conn
    except AppError:
        conn.execute("ROLLBACK")
        raise
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK")
        raise persistence_unavailable() from exc
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        try:
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise persistence_unavailable() from exc
