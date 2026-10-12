"""Reads the follower lists out of the zip X gives you from "Download an archive of your data"."""

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Archive:
    owner_id: str
    generated_at: datetime
    followers: list[str]
    following: list[str]


def _read_js(z: zipfile.ZipFile, name: str):
    # Each file is `window.<something> = <json>`.
    text = z.read(f"data/{name}").decode("utf-8")
    return json.loads(text.split("=", 1)[1])


def read_archive(path: Path) -> Archive:
    with zipfile.ZipFile(path) as z:
        manifest = _read_js(z, "manifest.js")
        followers = [row["follower"]["accountId"] for row in _read_js(z, "follower.js")]
        following = [row["following"]["accountId"] for row in _read_js(z, "following.js")]
    return Archive(
        owner_id=manifest["userInfo"]["accountId"],
        generated_at=datetime.fromisoformat(manifest["archiveInfo"]["generationDate"]),
        followers=followers,
        following=following,
    )
