import httpx
import pytest

from twitter_analysis.x_client import XClient, XError


def u(id: str) -> dict:
    return {"id": id, "username": f"u{id}", "name": f"U {id}", "profile_image_url": f"https://img/{id}"}


def make_client(handler) -> XClient:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.x.com")
    return XClient(http, access_token=lambda: "tok")


def test_followers_follows_pagination_until_the_last_page():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        assert req.url.path == "/2/users/42/followers"
        if "pagination_token" not in req.url.params:
            return httpx.Response(200, json={"data": [u("1"), u("2")], "meta": {"result_count": 2, "next_token": "p2"}})
        assert req.url.params["pagination_token"] == "p2"
        return httpx.Response(200, json={"data": [u("3")], "meta": {"result_count": 1}})

    users = make_client(handler).followers("42")

    assert [x["id"] for x in users] == ["1", "2", "3"]
    assert users[0]["profile_image_url"] == "https://img/1"
    assert seen[0].headers["authorization"] == "Bearer tok"
    assert seen[0].url.params["max_results"] == "1000"


def test_lookup_returns_only_existing_accounts_in_batches_of_100():
    batches = []

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/2/users"
        ids = req.url.params["ids"].split(",")
        batches.append(len(ids))
        # X lists suspended/deactivated accounts under "errors", not "data".
        return httpx.Response(
            200,
            json={
                "data": [u(i) for i in ids if i != "7"],
                "errors": [{"value": "7", "title": "Forbidden"}] if "7" in ids else [],
            },
        )

    users = make_client(handler).lookup([str(i) for i in range(150)])

    assert batches == [100, 50]
    assert len(users) == 149
    assert "7" not in {x["id"] for x in users}


def test_error_responses_raise():
    client = make_client(lambda req: httpx.Response(429, json={"title": "Too Many Requests"}))

    with pytest.raises(XError):
        client.followers("42")
