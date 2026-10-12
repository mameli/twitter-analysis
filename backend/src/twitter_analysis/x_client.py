"""Thin client for the few X API v2 endpoints a Sync needs. Every returned account is billed."""

from collections.abc import Callable

import httpx

USER_FIELDS = "profile_image_url"


class XError(Exception):
    pass


class XClient:
    def __init__(self, http: httpx.Client, access_token: Callable[[], str]) -> None:
        self.http = http
        self.access_token = access_token

    def _get(self, path: str, params: dict) -> dict:
        r = self.http.get(path, params=params, headers={"Authorization": f"Bearer {self.access_token()}"})
        if r.status_code != 200:
            raise XError(f"X API {path} returned {r.status_code}: {r.text}")
        return r.json()

    def _paginated(self, path: str) -> list[dict]:
        users: list[dict] = []
        params = {"max_results": 1000, "user.fields": USER_FIELDS}
        while True:
            body = self._get(path, params)
            users += body.get("data", [])
            next_token = body.get("meta", {}).get("next_token")
            if not next_token:
                return users
            params["pagination_token"] = next_token

    def me(self) -> dict:
        return self._get("/2/users/me", {})["data"]

    def followers(self, user_id: str) -> list[dict]:
        return self._paginated(f"/2/users/{user_id}/followers")

    def following(self, user_id: str) -> list[dict]:
        return self._paginated(f"/2/users/{user_id}/following")

    def lookup(self, ids: list[str]) -> list[dict]:
        """Accounts that still exist; suspended or deactivated ones are left out."""
        users: list[dict] = []
        for i in range(0, len(ids), 100):
            body = self._get("/2/users", {"ids": ",".join(ids[i : i + 100]), "user.fields": USER_FIELDS})
            users += body.get("data", [])
        return users
