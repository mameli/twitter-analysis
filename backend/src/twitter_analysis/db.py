import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    username TEXT,
    name TEXT,
    avatar_url TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY,
    taken_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_members (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    list TEXT NOT NULL CHECK (list IN ('followers', 'following')),
    account_id TEXT NOT NULL REFERENCES accounts(id),
    PRIMARY KEY (snapshot_id, list, account_id)
);

-- Changes in the Follower list, observed between two consecutive Snapshots.
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('new_follow', 'unfollow', 'exit')),
    account_id TEXT NOT NULL REFERENCES accounts(id),
    from_snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    to_snapshot_id INTEGER NOT NULL REFERENCES snapshots(id)
);

-- Every paid X API call, so the monthly budget can be enforced.
CREATE TABLE IF NOT EXISTS api_calls (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    resources INTEGER NOT NULL,
    cost_usd REAL NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
