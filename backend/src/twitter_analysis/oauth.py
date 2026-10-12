"""OAuth 2.0 (PKCE) login with the owner's X account; see docs/adr/0001 for why not an app-only token."""

import base64
import hashlib
import json
import secrets
import sqlite3
import time
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
SCOPES = "tweet.read users.read follows.read offline.access"


class NotAuthenticated(Exception):
    pass


class OAuth:
    def __init__(self, conn: sqlite3.Connection, client_id: str, client_secret: str | None, redirect_uri: str):
        self.conn = conn
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._pending: dict[str, str] = {}  # state -> PKCE code verifier

    def authorize_url(self) -> str:
        state = secrets.token_urlsafe(16)
        verifier = secrets.token_urlsafe(64)
        self._pending[state] = verifier
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        return f"{AUTHORIZE_URL}?" + urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": SCOPES,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )

    def complete(self, code: str, state: str) -> None:
        verifier = self._pending.pop(state, None)
        if verifier is None:
            raise NotAuthenticated("Unknown or expired login attempt, start again.")
        self._request_token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri, "code_verifier": verifier}
        )

    def is_authenticated(self) -> bool:
        return self._load() is not None

    def access_token(self) -> str:
        token = self._load()
        if token is None:
            raise NotAuthenticated("Log in with X before syncing.")
        if token["expires_at"] - time.time() < 60:
            try:
                token = self._request_token({"grant_type": "refresh_token", "refresh_token": token["refresh_token"]})
            except NotAuthenticated:
                self.logout()  # revoked or expired: show the login button again
                raise
        return token["access_token"]

    def logout(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM settings WHERE key = 'oauth_token'")

    def _request_token(self, data: dict) -> dict:
        # Confidential clients authenticate with Basic auth; public clients send only their client_id.
        auth = (self.client_id, self.client_secret) if self.client_secret else None
        r = httpx.post(TOKEN_URL, data={**data, "client_id": self.client_id}, auth=auth, timeout=30)
        if r.status_code != 200:
            raise NotAuthenticated(f"X token request failed ({r.status_code}): {r.text}")
        body = r.json()
        token = {
            "access_token": body["access_token"],
            "refresh_token": body["refresh_token"],  # X rotates it on every refresh
            "expires_at": time.time() + body["expires_in"],
        }
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('oauth_token', ?)", (json.dumps(token),)
            )
        return token

    def _load(self) -> dict | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = 'oauth_token'").fetchone()
        return json.loads(row[0]) if row else None
