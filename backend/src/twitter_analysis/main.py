import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import tracker
from .archive import read_archive
from .db import connect
from .oauth import NotAuthenticated, OAuth
from .x_client import XClient, XError


class ArchiveRequest(BaseModel):
    path: str


@dataclass
class XSettings:
    client_id: str
    client_secret: str | None
    redirect_uri: str
    frontend_url: str


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_app(
    db_path: Path,
    x_client=None,
    now: Callable[[], datetime] = _utcnow,
    budget_usd: float = 5.0,
    x_settings: XSettings | None = None,
) -> FastAPI:
    """Pass `x_client` to use a stand-in for the X API; otherwise `x_settings` is needed to log in to X."""
    conn = connect(db_path)
    app = FastAPI(title="Twitter Analysis")

    oauth = None
    if x_client is None:
        assert x_settings is not None
        oauth = OAuth(conn, x_settings.client_id, x_settings.client_secret, x_settings.redirect_uri)
        x_client = XClient(httpx.Client(base_url="https://api.x.com", timeout=30), oauth.access_token)

        @app.get("/api/auth/login")
        def login():
            if not x_settings.client_id:
                raise HTTPException(503, "X_CLIENT_ID is not set in backend/.env, see docs/setup-x.md.")
            return RedirectResponse(oauth.authorize_url())

        @app.get("/api/auth/callback")
        def callback(code: str, state: str):
            try:
                oauth.complete(code, state)
                tracker.check_owner(conn, x_client, now())
            except NotAuthenticated as e:
                raise HTTPException(400, str(e))
            except (tracker.Conflict, XError) as e:
                oauth.logout()
                raise HTTPException(409, str(e))
            return RedirectResponse(x_settings.frontend_url)

    @app.post("/api/archive")
    def import_archive(req: ArchiveRequest):
        path = Path(req.path).expanduser()
        if not path.is_file():
            raise HTTPException(400, f"File not found: {path}")
        try:
            tracker.import_archive(conn, read_archive(path))
        except tracker.Conflict as e:
            raise HTTPException(409, str(e))
        return {"ok": True}

    @app.post("/api/sync")
    def sync():
        try:
            tracker.sync(conn, x_client, now(), budget_usd)
        except (tracker.Conflict, NotAuthenticated) as e:
            raise HTTPException(409, str(e))
        except XError as e:
            raise HTTPException(502, str(e))
        return {"ok": True}

    @app.get("/api/dashboard")
    def dashboard():
        return {
            **tracker.dashboard(conn, now(), budget_usd),
            "authenticated": oauth.is_authenticated() if oauth else True,
        }

    return app


def app_from_env() -> FastAPI:
    return create_app(
        db_path=Path(os.environ.get("DB_PATH", "data.sqlite")),
        budget_usd=float(os.environ.get("MONTHLY_BUDGET_USD", "5")),
        x_settings=XSettings(
            client_id=os.environ.get("X_CLIENT_ID", ""),
            client_secret=os.environ.get("X_CLIENT_SECRET") or None,
            redirect_uri=os.environ.get("X_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/callback"),
            frontend_url=os.environ.get("FRONTEND_URL", "http://127.0.0.1:5173"),
        ),
    )
