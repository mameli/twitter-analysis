import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from twitter_analysis.main import create_app

OWNER_ID = "1000"


def user(id: str, username: str | None = None) -> dict:
    return {
        "id": id,
        "username": username or f"user{id}",
        "name": f"User {id}",
        "profile_image_url": f"https://pbs.twimg.com/{id}.jpg",
    }


class FakeX:
    """Stands in for the X API: tests set who follows whom and which accounts still exist."""

    def __init__(self) -> None:
        self.followers_list: list[dict] = []
        self.following_list: list[dict] = []
        self.active_ids: set[str] = set()
        self.calls: list[str] = []

    def followers(self, user_id: str) -> list[dict]:
        self.calls.append(f"followers:{user_id}")
        return self.followers_list

    def following(self, user_id: str) -> list[dict]:
        self.calls.append(f"following:{user_id}")
        return self.following_list

    def lookup(self, ids: list[str]) -> list[dict]:
        self.calls.append(f"lookup:{','.join(ids)}")
        return [user(id) for id in ids if id in self.active_ids]


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def write_archive(
    path: Path,
    followers: list[str],
    following: list[str],
    generated: str = "2026-09-28T09:00:00.000Z",
) -> Path:
    def js(var: str, key: str, ids: list[str]) -> str:
        rows = [{key: {"accountId": id, "userLink": f"https://twitter.com/intent/user?user_id={id}"}} for id in ids]
        return f"window.YTD.{var}.part0 = {json.dumps(rows)}"

    manifest = {
        "userInfo": {"accountId": OWNER_ID, "userName": "owner", "displayName": "Owner"},
        "archiveInfo": {"generationDate": generated},
    }
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("data/manifest.js", f"window.__THAR_CONFIG = {json.dumps(manifest)}")
        z.writestr("data/follower.js", js("follower", "follower", followers))
        z.writestr("data/following.js", js("following", "following", following))
    return path


@pytest.fixture
def x() -> FakeX:
    return FakeX()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(tmp_path: Path, x: FakeX, clock: Clock) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "db.sqlite", x_client=x, now=clock))


@pytest.fixture
def archive(tmp_path: Path):
    def make(followers: list[str], following: list[str], **kw) -> str:
        return str(write_archive(tmp_path / "archive.zip", followers, following, **kw))

    return make
