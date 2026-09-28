"""The optional "consult another doctor" chat, the consultation pages it can
add to the notebook, and the mission script export. Uses network-free
stand-ins for the chatbot."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from curelab.app import Settings, create_app
from curelab.consult import ConsultConfig, EchoConsultant, build_context

from .conftest import FIXTURE_PACK, ILLNESSES


class Recorder(EchoConsultant):
    """Echo stand-in that keeps what it was sent."""

    def __init__(self):
        super().__init__("echo")
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    async def stream(self, system, messages):
        self.calls.append((system, messages))
        async for piece in super().stream(system, messages):
            yield piece


def make_client(tmp_path, consult: ConsultConfig):
    settings = Settings(pack_dir=FIXTURE_PACK, illness_dir=ILLNESSES, data_dir=tmp_path, kernel="python3", consult=consult)
    return create_app(settings)


@pytest.fixture
def app(tmp_path):
    return make_client(tmp_path, ConsultConfig(provider="fake", model="echo"))


def start(client):
    r = client.post("/api/game/start", json={"campaign": "demo-one", "difficulty": "normal", "seed": 3})
    assert r.status_code == 200, r.text


def ask(client, path="/api/consult", **body):
    """POST a question and parse the server-sent events."""
    with client.stream("POST", path, json=body) as r:
        assert r.status_code == 200, r.read()
        raw = "".join(r.iter_text())
    events = []
    for block in raw.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def test_consult_is_off_without_a_key():
    assert not ConsultConfig.from_env({}).enabled
    assert not ConsultConfig.from_env({"CURELAB_CONSULT_PROVIDER": "anthropic"}).enabled


def test_provider_follows_the_keys():
    assert ConsultConfig.from_env({"OPENAI_API_KEY": "sk-x"}) == ConsultConfig("openai", "gpt-6-astra")
    assert ConsultConfig.from_env({"ANTHROPIC_API_KEY": "sk-ant-x"}) == ConsultConfig("anthropic", "claude-opus-5-5")
    both = {"OPENAI_API_KEY": "sk-x", "ANTHROPIC_API_KEY": "sk-ant-x"}
    assert ConsultConfig.from_env(both).provider == "openai"
    assert ConsultConfig.from_env({**both, "CURELAB_CONSULT_PROVIDER": "anthropic"}).provider == "anthropic"
    custom = ConsultConfig.from_env({"OPENAI_API_KEY": "sk-x", "CURELAB_CONSULT_MODEL": "gpt-6-sol"})
    assert custom.model == "gpt-6-sol"


def test_the_browser_never_sees_the_key():
    public = ConsultConfig.from_env({"OPENAI_API_KEY": "sk-secret"}).public()
    assert public == {"enabled": True, "provider": "openai", "label": "ChatGPT", "model": "gpt-6-astra"}
    assert "sk-secret" not in json.dumps(public)


def test_context_shares_the_mission_and_code_only_when_allowed():
    mission = {
        "number": 2,
        "title": "Count them",
        "finished": False,
        "briefing": "Add up the counts.",
        "task": ["Store the total in `total`."],
        "source": {"vignette": "datastructures.rst", "section": "More on Lists", "url": "https://docs.example/ds"},
    }
    ctx = build_context(tool="Python 3", campaign_title="Demo", finished=["1. Lists"], mission=mission,
                        code="total = sum(counts)", last_error="NameError: counts", language="python")
    for piece in ("Add up the counts.", "Store the total", "https://docs.example/ds", "total = sum(counts)",
                  "NameError: counts", "open, not finished yet", "1. Lists"):
        assert piece in ctx
    private = build_context(tool="Python 3", campaign_title="Demo", finished=[], mission=mission,
                            code="total = sum(counts)", last_error="NameError", include_code=False)
    assert "total = sum(counts)" not in private and "NameError" not in private
    assert "no mission open" in build_context(tool="Python 3", campaign_title="Demo", finished=[])


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


def test_disabled_consult_is_reported_and_refused(tmp_path):
    with TestClient(make_client(tmp_path, ConsultConfig())) as client:
        assert client.get("/api/meta").json()["consult"]["enabled"] is False
        start(client)
        assert client.post("/api/consult", json={"message": "hi"}).status_code == 409


def test_ask_streams_and_keeps_the_conversation(app, tmp_path):
    with TestClient(app) as client:
        assert client.get("/api/meta").json()["consult"] == {
            "enabled": True, "provider": "fake", "label": "Echo (test)", "model": "echo"}
        start(client)
        # no mission needed, no mistake needed: consult at any point
        events = ask(client, message="What is UMAP, mathematically?")
        kinds = [k for k, _ in events]
        assert kinds[-1] == "done" and kinds.count("delta") > 1
        answer = "".join(d["text"] for k, d in events if k == "delta")
        assert "What is UMAP, mathematically?" in answer
        done = events[-1][1]
        assert [m["role"] for m in done["messages"]] == ["user", "assistant"]
        assert done["messages"][1]["text"] == answer.strip()
        ask(client, message="And t-SNE?")
        assert len(client.get("/api/consult").json()["messages"]) == 4

    # saved with the game
    with TestClient(make_client(tmp_path, ConsultConfig(provider="fake", model="echo"))) as client:
        msgs = client.get("/api/consult").json()["messages"]
        assert [m["text"] for m in msgs if m["role"] == "user"] == ["What is UMAP, mathematically?", "And t-SNE?"]
        assert client.post("/api/consult/clear").json()["messages"] == []


def test_the_doctor_gets_the_mission_but_never_its_solution(app):
    recorder = Recorder()
    app.state.curelab.consultant = recorder
    mission = app.state.curelab.pack.campaign("demo-one").missions[0]
    with TestClient(app) as client:
        start(client)
        client.post(f"/api/missions/{mission.id}/start")
        client.post(f"/api/missions/{mission.id}/run", json={"code": "print(countz)"})
        ask(client, message="Why does this fail?", mission_id=mission.id, code="print(countz)")
        system, messages = recorder.calls[-1]
        sent = messages[-1]["content"]
        assert "coach" in system
        assert mission.title in sent and "print(countz)" in sent and "NameError" in sent
        assert mission.solution.strip() not in sent and mission.check.strip() not in sent
        # the second question resends the first one byte for byte (cacheable history)
        ask(client, message="And now?", mission_id=mission.id, code="", include_code=False)
        history = recorder.calls[-1][1]
        assert history[0]["content"] == sent and len(history) == 3
        assert "chose not to share" in history[-1]["content"]


def test_consultations_go_to_the_notebook_without_research_points(app):
    with TestClient(app) as client:
        start(client)
        long_question = "Explain how the shared nearest neighbour graph is built and pruned, please. " * 6
        ask(client, message=long_question)
        rp_before = client.get("/api/state").json()["game"]["rp"]
        r = client.post("/api/consult/notebook", json={"index": 1})
        assert r.status_code == 200, r.text
        note = r.json()["note"]
        assert note["kind"] == "consult" and note["title"].startswith("Consult: ")
        assert "**Consulting doctor**" in note["body"] and note["words"] >= 40
        assert note["qualifies"] is False
        assert r.json()["game"]["rp"] == rp_before
        whole = client.post("/api/consult/notebook", json={}).json()["note"]
        assert whole["title"].startswith("Consultation, day")
        notes = client.get("/api/notebook").json()["notes"]
        assert [n["kind"] for n in notes] == ["consult", "consult"]
        assert client.post("/api/consult/notebook", json={"index": 9}).status_code == 404


def test_script_export_has_every_mission_and_the_passing_code(app):
    campaign = app.state.curelab.pack.campaign("demo-one")
    first, second = campaign.missions[0], campaign.missions[1]
    with TestClient(app) as client:
        start(client)
        client.post(f"/api/missions/{first.id}/start")
        client.post(f"/api/missions/{first.id}/submit", json={"code": "counts = [1, 3, 4]"})  # wrong
        r = client.post(f"/api/missions/{first.id}/submit", json={"code": "counts = [3, 1, 4]  # mine"})
        assert r.json()["outcome"]["passed"]
        res = client.get("/api/notebook/script")
        assert res.status_code == 200
        assert 'filename="curelab-demo-one.py"' in res.headers["content-disposition"]
        script = res.text
        assert f"# Mission 1: {first.title}" in script and f"# Mission 2: {second.title}" in script
        assert "counts = [3, 1, 4]  # mine" in script and "counts = [1, 3, 4]" not in script
        assert script.count("# (not passed yet)") == len(campaign.missions) - 1
        briefing_line = first.briefing.strip().splitlines()[0]
        assert "# " + app.state.curelab.illnesses[campaign.illness].fill(briefing_line) in script
