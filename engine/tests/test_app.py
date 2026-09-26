"""End-to-end API tests against a real Jupyter kernel (ipykernel) using the
Python fixture pack. This exercises exactly the code path the R pack uses."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from curelab.app import Settings, create_app

from .conftest import FIXTURE_PACK, ILLNESSES


@pytest.fixture
def client(tmp_path):
    settings = Settings(pack_dir=FIXTURE_PACK, illness_dir=ILLNESSES, data_dir=tmp_path, kernel="python3")
    app = create_app(settings)
    app.state.curelab.balance.research_points.min_read_seconds = 0.2
    with TestClient(app) as c:
        yield c


def start(client, campaign="demo-one", seed=11):
    r = client.post("/api/game/start", json={"campaign": campaign, "difficulty": "normal", "seed": seed})
    assert r.status_code == 200, r.text
    return r.json()


def test_meta_and_locking(client):
    meta = client.get("/api/meta").json()
    ids = {c["id"]: c for c in meta["campaigns"]}
    assert ids["demo-one"]["locked"] is False
    assert ids["demo-two"]["locked"] is True
    assert ids["demo-one"]["patient"]["name"] == "Walter Brandt"
    assert {d["id"] for d in meta["difficulties"]} == {"casual", "normal", "brutal"}
    r = client.post("/api/game/start", json={"campaign": "demo-two"})
    assert r.status_code == 403


def test_full_mission_loop(client):
    snap = start(client)
    assert snap["game"]["status"] == "playing"
    assert snap["patient"]["first_name"] == "Walter"

    detail = client.get("/api/missions/demo-m01-list").json()
    assert detail["briefing"].startswith("Walter's first samples")
    assert detail["hints"] == [] and detail["hint_total"] == 3
    assert detail["source"]["site_url"].endswith("datastructures.html")

    r = client.post("/api/missions/demo-m01-list/start")
    assert r.status_code == 200, r.text

    # free run: no penalty even on error, debug help offered
    r = client.post("/api/missions/demo-m01-list/run", json={"code": "print(countz)"}).json()
    assert r["execution"]["status"] == "error"
    assert any("variable or function" in h for h in r["debug"])
    assert r["game"]["errors"] == 0

    r = client.post("/api/missions/demo-m01-list/run", json={"code": "print(1 + 1)\n2 * 21"}).json()
    assert r["execution"]["stdout"].strip() == "2"
    assert r["execution"]["results"] == ["42"]

    # graded wrong answer (check fails) -> disease evolves
    r = client.post("/api/missions/demo-m01-list/submit", json={"code": "counts = [1, 3, 4]"}).json()
    assert r["outcome"]["graded"] and not r["outcome"]["passed"]
    assert "should be [3, 1, 4]" in r["outcome"]["message"]
    assert "wrong values" in " ".join(r["outcome"]["debug"])
    assert r["game"]["errors"] == 1
    assert [e["kind"] for e in r["events"]] == ["trait"]

    # graded error (exception) -> also evolves
    r = client.post("/api/missions/demo-m01-list/submit", json={"code": "counts = [3, 1, 4"}).json()
    assert r["outcome"]["execution"]["status"] == "error"
    assert r["game"]["errors"] == 2

    # debug endpoint explains the last error for free
    dbg = client.post("/api/missions/demo-m01-list/debug").json()
    assert "SyntaxError" in dbg["error"]
    assert dbg["help"]

    # correct answer
    since = r["cursor"]
    r = client.post("/api/missions/demo-m01-list/submit", json={"code": "counts = [3, 1, 4]", "since": since}).json()
    assert r["outcome"]["passed"]
    assert r["game"]["research"] == 30
    assert [e["kind"] for e in r["events"]] == ["mission"]
    assert r["game"]["missions"][1]["status"] == "available"

    # next mission gets its own setup (a fresh kernel with the checkpoint state)
    assert client.post("/api/missions/demo-m02-sum/start").status_code == 200
    r = client.post("/api/missions/demo-m02-sum/run", json={"code": "counts"}).json()
    assert r["execution"]["results"] == ["[3, 1, 4]"]


def test_locked_mission_rejected(client):
    start(client)
    assert client.post("/api/missions/demo-m02-sum/start").status_code == 409
    assert client.post("/api/missions/demo-m02-sum/submit", json={"code": "x=1"}).status_code == 409


def test_hints_notebook_and_export(client):
    start(client)
    # no RP yet
    assert client.post("/api/missions/demo-m01-list/hint").status_code == 409
    nb = client.get("/api/notebook").json()
    assert nb["pages"][0]["id"] == "demo-nb01" and nb["pages"][0]["read"] is False
    assert nb["pages"][0]["blocks"][1]["source"]["pinned_url"].startswith("https://github.com/python/cpython/blob/")

    # reading requires opening first and a short dwell
    assert client.post("/api/notebook/pages/demo-nb01/read", json={"token": "nope"}).status_code == 409
    token = client.post("/api/notebook/pages/demo-nb01/open").json()["token"]
    assert client.post("/api/notebook/pages/demo-nb01/read", json={"token": token}).status_code == 409
    time.sleep(0.25)
    snap = client.post("/api/notebook/pages/demo-nb01/read", json={"token": token}).json()
    assert snap["game"]["rp"] == 2

    h = client.post("/api/missions/demo-m01-list/hint").json()
    assert h["tier"] == 0 and "square brackets" in h["text"]
    assert h["game"]["rp"] == 1
    assert client.get("/api/missions/demo-m01-list").json()["hints"] == [h["text"]]

    # own notes: need 40 words and a mission attempt before they pay
    note = client.post("/api/notebook/notes", json={"title": "QC", "body": "short"}).json()["note"]
    assert note["qualifies"] is False
    long_body = "Filtering removes low quality cells before normalization. " * 8
    r = client.put(f"/api/notebook/notes/{note['id']}", json={"body": long_body}).json()
    assert r["note"]["qualifies"] is True
    assert r["game"]["rp"] == 1  # capped: no mission attempted yet
    client.post("/api/missions/demo-m01-list/start")
    r = client.post("/api/missions/demo-m01-list/submit", json={"code": "counts = [3, 1, 4]"}).json()
    assert r["game"]["rp"] == 2  # the attempt lifted the cap
    assert r["game"]["notes"] == {"qualifying": 1, "awarded": 1, "cap": 1}

    mine = client.get("/api/notebook/export?scope=mine")
    assert mine.status_code == 200
    assert "attachment" in mine.headers["content-disposition"]
    assert "Filtering removes low quality cells" in mine.text
    assert "Reference pages" not in mine.text
    everything = client.get("/api/notebook/export?scope=all").text
    assert "Reference pages" in everything and "Mission log" in everything


def test_quiz_and_win_unlocks_next_campaign(client):
    start(client)
    for mid, code in [
        ("demo-m01-list", "counts = [3, 1, 4]"),
        ("demo-m02-sum", "total = sum(counts)"),
        ("demo-m03-sort", "ranked = sorted(counts)"),
    ]:
        assert client.post(f"/api/missions/{mid}/start").status_code == 200
        r = client.post(f"/api/missions/{mid}/submit", json={"code": code}).json()
        assert r["outcome"]["passed"], r["outcome"]
    snap = client.post("/api/quizzes/demo-q01/answer", json={"choice": 0}).json()
    assert snap["correct"] is False and snap["game"]["errors"] == 1
    snap = client.post("/api/quizzes/demo-q01/answer", json={"choice": 1}).json()
    q = next(q for q in snap["game"]["quizzes"] if q["id"] == "demo-q01")
    assert q["status"] == "completed" and q["explanation"]
    snap = client.post("/api/quizzes/demo-q02/answer", json={"choice": 1}).json()
    assert snap["game"]["status"] == "won"
    meta = client.get("/api/meta").json()
    two = next(c for c in meta["campaigns"] if c["id"] == "demo-two")
    assert two["locked"] is False and meta["history"][-1]["status"] == "won"


def test_heartbeat_advances_only_when_visible(client):
    start(client)
    client.post("/api/heartbeat", json={"visible": True})
    time.sleep(1.1)
    a = client.post("/api/heartbeat", json={"visible": True}).json()["game"]["clock"]
    assert 1.0 <= a <= 3.0
    time.sleep(1.1)
    b = client.post("/api/heartbeat", json={"visible": False}).json()["game"]["clock"]
    assert b == a


def test_state_persists_across_restart(tmp_path):
    settings = Settings(pack_dir=FIXTURE_PACK, illness_dir=ILLNESSES, data_dir=tmp_path, kernel="python3")
    with TestClient(create_app(settings)) as c:
        start(c, seed=5)
        c.post("/api/quizzes/demo-q01/answer", json={"choice": 0})  # locked -> 409, no change
        c.post("/api/notebook/notes", json={"title": "keep me", "body": "hello"})
    with TestClient(create_app(settings)) as c:
        snap = c.get("/api/state").json()
        assert snap["game"]["campaign"] == "demo-one"
        notes = c.get("/api/notebook").json()["notes"]
        assert notes[0]["title"] == "keep me"
