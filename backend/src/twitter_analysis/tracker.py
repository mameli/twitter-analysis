"""Snapshots of Followers/Followings and the dashboard built from them. Vocabulary: see CONTEXT.md."""

import sqlite3
from datetime import UTC, datetime, timedelta

from .archive import Archive

FOLLOW_CHURNER_WINDOW = timedelta(days=14)

# X API pay-per-use prices, per returned account (docs.x.com/x-api/getting-started/pricing).
# Reading your own Followers/Followings qualifies for the owned-read rate, see docs/adr/0001.
OWNED_READ_USD = 0.001
USER_READ_USD = 0.010


class Conflict(Exception):
    """The requested operation is not allowed in the current state."""


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _latest_snapshot(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT id, taken_at FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()


def _save_snapshot(conn: sqlite3.Connection, taken_at: datetime, followers: list[str], following: list[str]) -> int:
    cur = conn.execute("INSERT INTO snapshots (taken_at) VALUES (?)", (_iso(taken_at),))
    snapshot_id = cur.lastrowid
    assert snapshot_id is not None
    for list_name, ids in (("followers", followers), ("following", following)):
        conn.executemany("INSERT OR IGNORE INTO accounts (id) VALUES (?)", [(id,) for id in ids])
        conn.executemany(
            "INSERT INTO snapshot_members (snapshot_id, list, account_id) VALUES (?, ?, ?)",
            [(snapshot_id, list_name, id) for id in ids],
        )
    return snapshot_id


def import_archive(conn: sqlite3.Connection, archive: Archive) -> None:
    if _latest_snapshot(conn):
        raise Conflict("The archive can only be imported as the first Snapshot.")
    with conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('owner_id', ?)", (archive.owner_id,))
        _save_snapshot(conn, archive.generated_at, archive.followers, archive.following)


def _save_profiles(conn: sqlite3.Connection, users: list[dict]) -> None:
    conn.executemany(
        """INSERT INTO accounts (id, username, name, avatar_url) VALUES (:id, :username, :name, :avatar_url)
           ON CONFLICT (id) DO UPDATE SET
             username = excluded.username, name = excluded.name, avatar_url = excluded.avatar_url""",
        [
            {"id": u["id"], "username": u["username"], "name": u["name"], "avatar_url": u.get("profile_image_url")}
            for u in users
        ],
    )


def _month_spend(conn: sqlite3.Connection, now: datetime) -> float:
    month_start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM api_calls WHERE at >= ?", (_iso(month_start),))
    return round(row.fetchone()[0], 4)


def _paid_call(conn: sqlite3.Connection, now: datetime, endpoint: str, price: float, call) -> list[dict]:
    users = call()
    # Committed on its own: the money is spent even if the rest of the Sync fails.
    with conn:
        conn.execute(
            "INSERT INTO api_calls (at, endpoint, resources, cost_usd) VALUES (?, ?, ?, ?)",
            (_iso(now), endpoint, len(users), len(users) * price),
        )
    return users


def check_owner(conn: sqlite3.Connection, x, now: datetime) -> None:
    """The logged-in X account must be the archive's owner, or reads lose the owned-read price."""
    [me] = _paid_call(conn, now, "me", USER_READ_USD, lambda: [x.me()])
    owner_id = conn.execute("SELECT value FROM settings WHERE key = 'owner_id'").fetchone()[0]
    if me["id"] != owner_id:
        raise Conflict(f"Logged in as @{me['username']}, but the archive belongs to another account.")


def sync(conn: sqlite3.Connection, x, now: datetime, budget_usd: float) -> None:
    previous = _latest_snapshot(conn)
    if not previous:
        raise Conflict("Import the X archive before the first Sync.")
    owner_id = conn.execute("SELECT value FROM settings WHERE key = 'owner_id'").fetchone()[0]

    previous_size = conn.execute(
        "SELECT COUNT(*) FROM snapshot_members WHERE snapshot_id = ?", (previous["id"],)
    ).fetchone()[0]
    if _month_spend(conn, now) + previous_size * OWNED_READ_USD > budget_usd:
        raise Conflict(f"A Sync now could exceed this month's ${budget_usd:.2f} budget.")

    followers = _paid_call(conn, now, "followers", OWNED_READ_USD, lambda: x.followers(owner_id))
    following = _paid_call(conn, now, "following", OWNED_READ_USD, lambda: x.following(owner_id))

    before = _members(conn, previous["id"], "followers")
    after = {u["id"] for u in followers}
    exited = sorted(before - after)
    if _month_spend(conn, now) + len(exited) * USER_READ_USD > budget_usd:
        raise Conflict(
            f"Checking {len(exited)} vanished Followers would exceed this month's ${budget_usd:.2f} budget."
        )
    # An account that vanished might have been suspended or deactivated rather than unfollowing.
    still_active = _paid_call(conn, now, "lookup", USER_READ_USD, lambda: x.lookup(exited)) if exited else []
    unfollowed = {u["id"] for u in still_active}

    changes = [("new_follow", id) for id in after - before] + [
        ("unfollow" if id in unfollowed else "exit", id) for id in exited
    ]
    with conn:
        _save_profiles(conn, followers + following + still_active)
        current = _save_snapshot(conn, now, [u["id"] for u in followers], [u["id"] for u in following])
        conn.executemany(
            "INSERT INTO events (type, account_id, from_snapshot_id, to_snapshot_id) VALUES (?, ?, ?, ?)",
            [(type, id, previous["id"], current) for type, id in changes],
        )


def _members(conn: sqlite3.Connection, snapshot_id: int, list_name: str) -> set[str]:
    rows = conn.execute(
        "SELECT account_id FROM snapshot_members WHERE snapshot_id = ? AND list = ?", (snapshot_id, list_name)
    )
    return {r[0] for r in rows}


def _account(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "username": r["username"], "name": r["name"], "avatar_url": r["avatar_url"]}


def dashboard(conn: sqlite3.Connection, now: datetime, budget_usd: float) -> dict:
    latest = _latest_snapshot(conn)
    followers = _members(conn, latest["id"], "followers") if latest else set()
    following = _members(conn, latest["id"], "following") if latest else set()

    history = conn.execute(
        """SELECT s.taken_at, COUNT(m.account_id) AS followers
           FROM snapshots s LEFT JOIN snapshot_members m ON m.snapshot_id = s.id AND m.list = 'followers'
           GROUP BY s.id ORDER BY s.id"""
    )
    event_rows = conn.execute(
        """SELECT e.type, a.*, f.taken_at AS from_at, t.taken_at AS to_at,
             (SELECT s.taken_at FROM events nf JOIN snapshots s ON s.id = nf.to_snapshot_id
              WHERE nf.account_id = e.account_id AND nf.type = 'new_follow' AND nf.id < e.id
              ORDER BY nf.id DESC LIMIT 1) AS followed_at
           FROM events e
           JOIN accounts a ON a.id = e.account_id
           JOIN snapshots f ON f.id = e.from_snapshot_id
           JOIN snapshots t ON t.id = e.to_snapshot_id
           ORDER BY e.id DESC"""
    ).fetchall()
    events = [
        {
            "type": r["type"],
            "account": _account(r),
            "between": [r["from_at"], r["to_at"]],
            "churner": r["type"] == "unfollow"
            and r["followed_at"] is not None
            and datetime.fromisoformat(r["to_at"]) - datetime.fromisoformat(r["followed_at"]) <= FOLLOW_CHURNER_WINDOW,
            "still_following": r["id"] in following,
        }
        for r in event_rows
    ]
    one_way = sorted(following - followers)
    one_way_rows = conn.execute(
        f"SELECT * FROM accounts WHERE id IN ({','.join('?' * len(one_way))}) ORDER BY username", one_way
    )
    month_ago = now - timedelta(days=30)

    return {
        "archive_imported": latest is not None,
        "last_snapshot_at": latest["taken_at"] if latest else None,
        "counts": {
            "followers": len(followers),
            "following": len(following),
            "mutuals": len(followers & following),
            "unfollows_30d": sum(
                1 for e in events if e["type"] == "unfollow" and datetime.fromisoformat(e["between"][1]) >= month_ago
            ),
        },
        "follower_history": [dict(r) for r in history],
        "events": events,
        "one_way_following": [_account(r) for r in one_way_rows],
        "spend": {"month_usd": _month_spend(conn, now), "budget_usd": budget_usd},
    }
