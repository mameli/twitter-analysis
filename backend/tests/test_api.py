from datetime import timedelta

from conftest import OWNER_ID, user
from fastapi.testclient import TestClient

from twitter_analysis.main import create_app


def events(client, type=None):
    evs = client.get("/api/dashboard").json()["events"]
    return [e for e in evs if type is None or e["type"] == type]


def test_imported_archive_becomes_the_first_snapshot(client, archive):
    r = client.post("/api/archive", json={"path": archive(["1", "2", "3"], ["2", "3", "4", "5"])})
    assert r.status_code == 200

    d = client.get("/api/dashboard").json()
    assert d["archive_imported"] is True
    assert d["counts"] == {"followers": 3, "following": 4, "mutuals": 2, "unfollows_30d": 0}
    assert d["follower_history"] == [{"taken_at": "2026-09-28T09:00:00+00:00", "followers": 3}]
    assert d["events"] == []


def test_sync_is_refused_until_the_archive_is_imported(client, x):
    r = client.post("/api/sync")
    assert r.status_code == 409
    assert x.calls == []


def test_archive_can_only_be_imported_once(client, archive):
    path = archive(["1"], ["2"])
    assert client.post("/api/archive", json={"path": path}).status_code == 200
    assert client.post("/api/archive", json={"path": path}).status_code == 409


def test_sync_records_new_follows_with_their_profile(client, archive, x, clock):
    client.post("/api/archive", json={"path": archive(["1"], [])})
    x.followers_list = [user("1"), user("2", "newcomer")]

    assert client.post("/api/sync").status_code == 200

    assert x.calls == [f"followers:{OWNER_ID}", f"following:{OWNER_ID}"]
    [ev] = events(client)
    assert ev["type"] == "new_follow"
    assert ev["account"] == {
        "id": "2",
        "username": "newcomer",
        "name": "User 2",
        "avatar_url": "https://pbs.twimg.com/2.jpg",
    }
    assert ev["between"] == ["2026-09-28T09:00:00+00:00", "2026-10-01T12:00:00+00:00"]


def test_exits_are_unfollows_only_if_the_account_still_exists(client, archive, x):
    client.post("/api/archive", json={"path": archive(["1", "2", "3"], [])})
    x.followers_list = [user("1")]
    x.active_ids = {"2"}  # "3" was suspended or deactivated

    client.post("/api/sync")

    assert x.calls[-1] == "lookup:2,3"
    [unfollow] = events(client, "unfollow")
    assert unfollow["account"]["username"] == "user2"  # profile filled in by the lookup
    [exit] = events(client, "exit")
    assert exit["account"] == {"id": "3", "username": None, "name": None, "avatar_url": None}


def test_no_lookup_when_nobody_left(client, archive, x):
    client.post("/api/archive", json={"path": archive(["1"], [])})
    x.followers_list = [user("1")]

    client.post("/api/sync")

    assert not any(c.startswith("lookup") for c in x.calls)


def test_unfollow_within_14_days_of_the_new_follow_is_a_follow_churner(client, archive, x, clock):
    client.post("/api/archive", json={"path": archive(["old"], [])})
    x.active_ids = {"old", "quick", "slow"}

    x.followers_list = [user("old"), user("quick"), user("slow")]
    client.post("/api/sync")  # 2026-10-01: quick and slow start following

    clock.now += timedelta(days=13)
    x.followers_list = [user("slow")]
    client.post("/api/sync")  # quick and old leave

    clock.now += timedelta(days=2)
    x.followers_list = []
    client.post("/api/sync")  # slow leaves, 15 days after its New follow

    churner = {e["account"]["id"]: e["churner"] for e in events(client, "unfollow")}
    assert churner == {"quick": True, "old": False, "slow": False}


def test_unfollow_shows_whether_the_owner_still_follows_them(client, archive, x):
    client.post("/api/archive", json={"path": archive(["mutual", "follower_only"], ["mutual"])})
    x.active_ids = {"mutual", "follower_only"}
    x.following_list = [user("mutual")]

    client.post("/api/sync")

    still = {e["account"]["id"]: e["still_following"] for e in events(client, "unfollow")}
    assert still == {"mutual": True, "follower_only": False}


def test_one_way_followings_are_followings_that_are_not_followers(client, archive, x):
    client.post("/api/archive", json={"path": archive([], [])})
    x.followers_list = [user("1")]
    x.following_list = [user("1"), user("2", "celebrity")]

    client.post("/api/sync")

    one_way = client.get("/api/dashboard").json()["one_way_following"]
    assert [a["username"] for a in one_way] == ["celebrity"]


def test_unfollow_count_covers_the_last_30_days(client, archive, x, clock):
    client.post("/api/archive", json={"path": archive(["1", "2"], [])})
    x.active_ids = {"1", "2"}
    x.followers_list = [user("2")]
    client.post("/api/sync")  # 1 unfollows

    clock.now += timedelta(days=20)
    x.followers_list = []
    client.post("/api/sync")  # 2 unfollows

    clock.now += timedelta(days=15)
    counts = client.get("/api/dashboard").json()["counts"]
    assert counts["unfollows_30d"] == 1


def test_spend_is_tracked_per_returned_account(client, archive, x):
    client.post("/api/archive", json={"path": archive(["1", "2", "gone"], [])})
    x.active_ids = {"gone"}
    x.followers_list = [user("1"), user("2")]
    x.following_list = [user("1")]

    client.post("/api/sync")

    # 3 owned reads at $0.001 + 1 looked-up account at $0.010
    assert client.get("/api/dashboard").json()["spend"] == {"month_usd": 0.013, "budget_usd": 5.0}


def test_sync_is_refused_when_it_could_exceed_the_monthly_budget(tmp_path, archive, x, clock):
    client = TestClient(create_app(db_path=tmp_path / "db.sqlite", x_client=x, now=clock, budget_usd=0.005))
    client.post("/api/archive", json={"path": archive(["1", "2"], ["1"])})
    x.followers_list = [user("1"), user("2")]
    x.following_list = [user("1")]
    assert client.post("/api/sync").status_code == 200  # spends $0.003

    calls = len(x.calls)
    r = client.post("/api/sync")  # another $0.003 would go past $0.005
    assert r.status_code == 409
    assert len(x.calls) == calls

    clock.now += timedelta(days=31)  # new month, fresh budget
    assert client.post("/api/sync").status_code == 200


def test_sync_stops_before_a_lookup_that_would_exceed_the_budget(tmp_path, archive, x, clock):
    client = TestClient(create_app(db_path=tmp_path / "db.sqlite", x_client=x, now=clock, budget_usd=0.02))
    client.post("/api/archive", json={"path": archive(["1", "2", "3"], [])})
    x.followers_list = []  # 3 exits: $0.03 of lookups on top of the reads

    r = client.post("/api/sync")

    assert r.status_code == 409
    assert not any(c.startswith("lookup") for c in x.calls)
    assert client.get("/api/dashboard").json()["events"] == []
