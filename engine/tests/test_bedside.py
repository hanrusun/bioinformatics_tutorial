"""The optional bedside chat: the learner talks to the fictional patient,
who answers in character from the game state. Network-free."""

from __future__ import annotations

from fastapi.testclient import TestClient

from curelab import bedside
from curelab.consult import ConsultConfig

from .test_consult import Recorder, ask, make_client, start


def say(client, message):
    """POST to the bedside and parse the server-sent events."""
    return ask(client, message=message, path="/api/bedside")


def test_adults_talk_and_toddlers_babble(nsclc, neuroblastoma):
    walter = bedside.system_prompt(nsclc)
    assert "You are playing Walter Brandt" in walter and "Speak as Walter" in walter
    assert "keeps bees" in walter and "not a scientist" in walter
    assert not bedside.toddler(nsclc)

    mia = bedside.system_prompt(neuroblastoma)
    assert bedside.toddler(neuroblastoma) and bedside.companion_name(neuroblastoma) == "Grace"
    assert "babble" in mia and "emojis" in mia
    # Grace is sometimes in the room, not the voice of every answer
    assert "Grace is not always in the room" in mia and "Most replies are Mia alone" in mia
    assert "Her mom, Grace, visits often." in mia


def test_the_chart_follows_the_game(game):
    chart = bedside.chart(game)
    assert "Day in hospital: 1" in chart and bedside.FEELINGS["stable"] in chart
    assert "only just started" in chart
    event = game.wrong_attempt("mission m1")
    chart = bedside.chart(game)
    assert event.text in chart or "disease is changing" in chart
    game.state.research = 80
    assert "may be close" in bedside.chart(game)
    game.state.status, game.state.stage = "won", "cured"
    chart = bedside.chart(game)
    assert bedside.FEELINGS["cured"] in chart and game.illness.fill(game.illness.cure_note) in chart
    # no numbers from the game mechanics
    assert "health" not in chart.lower() and "%" not in chart


def test_bedside_is_its_own_conversation(tmp_path):
    app = make_client(tmp_path, ConsultConfig(provider="fake", model="echo"))
    recorder = Recorder()
    app.state.curelab.bedside_consultant = recorder
    with TestClient(app) as client:
        start(client)
        view = client.get("/api/bedside").json()
        assert view["patient"] == "Walter" and view["open"] is True and view["messages"] == []
        events = say(client, "How are you feeling?")
        assert events[-1][0] == "done"
        assert "How are you feeling?" in "".join(d["text"] for k, d in events if k == "delta")
        system, messages = recorder.calls[-1]
        assert system == bedside.system_prompt(app.state.curelab.game.illness)
        assert messages[-1]["content"].startswith("Bedside chart") and "How are you feeling?" in messages[-1]["content"]
        say(client, "Did you sleep?")
        history = recorder.calls[-1][1]
        assert history[0]["content"] == messages[-1]["content"] and len(history) == 3
        # the consulting doctor's chat is untouched
        assert client.get("/api/consult").json()["messages"] == []
        assert [m["text"] for m in client.get("/api/bedside").json()["messages"][::2]] == [
            "How are you feeling?", "Did you sleep?"]

    with TestClient(make_client(tmp_path, ConsultConfig(provider="fake", model="echo"))) as client:
        assert len(client.get("/api/bedside").json()["messages"]) == 4  # saved with the game
        assert client.post("/api/bedside/clear").json()["messages"] == []


def test_bedside_chats_go_to_the_notebook_without_research_points(tmp_path):
    with TestClient(make_client(tmp_path, ConsultConfig(provider="fake", model="echo"))) as client:
        start(client)
        say(client, "How are you feeling today, Walter? " * 8)
        rp = client.get("/api/state").json()["game"]["rp"]
        r = client.post("/api/bedside/notebook", json={"index": 0})
        assert r.status_code == 200, r.text
        note = r.json()["note"]
        assert note["kind"] == "bedside" and note["title"].startswith("Bedside: ")
        assert "**Walter**:" in note["body"] and note["qualifies"] is False
        assert r.json()["game"]["rp"] == rp
        whole = client.post("/api/bedside/notebook", json={}).json()["note"]
        assert whole["title"].startswith("Bedside chats with Walter, day")


def test_no_bedside_chat_after_the_patient_dies_or_without_a_key(tmp_path):
    app = make_client(tmp_path, ConsultConfig(provider="fake", model="echo"))
    with TestClient(app) as client:
        start(client)
        say(client, "Hello")
        app.state.curelab.game._lose()
        assert client.get("/api/bedside").json()["open"] is False
        r = client.post("/api/bedside", json={"message": "Hello?"})
        assert r.status_code == 409 and "Walter has died" in r.json()["detail"]
        assert len(client.get("/api/bedside").json()["messages"]) == 2  # still there to read
    with TestClient(make_client(tmp_path / "off", ConsultConfig())) as client:
        start(client)
        assert client.post("/api/bedside", json={"message": "Hello"}).status_code == 409
