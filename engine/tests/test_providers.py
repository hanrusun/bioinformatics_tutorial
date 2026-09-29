"""The chat providers: which one a .env picks, what the browser learns, and
how each consultant talks to its service. Network-free: the Claude-plan
consultant gets a stand-in for the Agent SDK's ``query`` that replays the
SDK's own message types, and the OpenAI-compatible one a failing client."""

from __future__ import annotations

import asyncio
import json

import httpx
import openai
import pytest

claude_agent_sdk = pytest.importorskip("claude_agent_sdk")
from claude_agent_sdk import AssistantMessage, ResultMessage, StreamEvent, TextBlock  # noqa: E402

from curelab.consult import (  # noqa: E402
    GEMINI_BASE_URL,
    ClaudePlanConsultant,
    ConsultConfig,
    ConsultError,
    OpenAIConsultant,
    make_consultant,
    plan_prompt,
)

SECRETS = {
    "OPENAI_API_KEY": "sk-openai-secret",
    "ANTHROPIC_API_KEY": "sk-ant-secret",
    "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-secret",
    "GEMINI_API_KEY": "gemini-secret",
    "CURELAB_CONSULT_BASE_URL": "https://api.groq.com/openai/v1",
    "CURELAB_CONSULT_API_KEY": "gsk-secret",
}


def collect(consultant, system="be kind", messages=None):
    async def run():
        return [piece async for piece in consultant.stream(system, messages or [{"role": "user", "content": "hi"}])]

    return asyncio.run(run())


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def test_each_credential_switches_its_provider_on():
    assert ConsultConfig.from_env({"CLAUDE_CODE_OAUTH_TOKEN": "t"}).provider == "claude-plan"
    gemini = ConsultConfig.from_env({"GEMINI_API_KEY": "k"})
    assert (gemini.provider, gemini.model, gemini.patient_model) == (
        "gemini", "gemini-flash-latest", "gemini-flash-lite-latest")
    custom = ConsultConfig.from_env({"CURELAB_CONSULT_BASE_URL": "https://openrouter.ai/api/v1",
                                     "CURELAB_CONSULT_MODEL": "some/model:free"})
    assert (custom.provider, custom.label, custom.model, custom.base_url) == (
        "custom", "OpenRouter", "some/model:free", "https://openrouter.ai/api/v1")
    local = ConsultConfig.from_env({"CURELAB_CONSULT_BASE_URL": "http://host.docker.internal:11434/v1"})
    assert local.label == "Ollama"
    assert ConsultConfig.from_env({"CURELAB_CONSULT_BASE_URL": "https://llm.example.org/v1"}).label == "llm.example.org"


def test_order_when_several_are_set_and_explicit_choice():
    assert ConsultConfig.from_env(SECRETS).provider == "openai"
    no_openai = {k: v for k, v in SECRETS.items() if k != "OPENAI_API_KEY"}
    assert ConsultConfig.from_env(no_openai).provider == "anthropic"
    for provider in ("claude-plan", "gemini", "custom"):
        assert ConsultConfig.from_env({**SECRETS, "CURELAB_CONSULT_PROVIDER": provider}).provider == provider
    # choosing a provider whose credential is missing leaves the chats off
    assert not ConsultConfig.from_env({"OPENAI_API_KEY": "k", "CURELAB_CONSULT_PROVIDER": "gemini"}).enabled


def test_the_patient_can_have_its_own_model():
    env = {"ANTHROPIC_API_KEY": "k", "CURELAB_BEDSIDE_MODEL": "claude-haiku-4-5-20251001"}
    config = ConsultConfig.from_env(env)
    assert (config.model, config.patient_model) == ("claude-opus-5-5", "claude-haiku-4-5-20251001")
    assert ConsultConfig.from_env({"GEMINI_API_KEY": "k", "CURELAB_CONSULT_MODEL": "gemini-x"}).patient_model == (
        "gemini-flash-lite-latest")


def test_the_browser_never_sees_a_key_or_token():
    for provider in ("openai", "anthropic", "claude-plan", "gemini", "custom"):
        public = ConsultConfig.from_env({**SECRETS, "CURELAB_CONSULT_PROVIDER": provider}).public()
        assert public["enabled"] and public["provider"] == provider
        dumped = json.dumps(public)
        assert not any(secret in dumped for key, secret in SECRETS.items() if key != "CURELAB_CONSULT_BASE_URL")
    plan = ConsultConfig.from_env({"CLAUDE_CODE_OAUTH_TOKEN": "t"}).public()
    assert plan["label"] == "Claude (your plan)" and plan["model"] == "your plan's default model"


def test_make_consultant_wires_each_service(monkeypatch):
    for key, value in SECRETS.items():
        monkeypatch.setenv(key, value)
    gemini = make_consultant(ConsultConfig.from_env({"GEMINI_API_KEY": "k"}))
    assert isinstance(gemini, OpenAIConsultant) and str(gemini.client.base_url) == GEMINI_BASE_URL
    assert gemini.client.api_key == "gemini-secret" and gemini.key_env == "GEMINI_API_KEY"
    patient = make_consultant(ConsultConfig.from_env({"GEMINI_API_KEY": "k"}), "bedside")
    assert patient.model == "gemini-flash-lite-latest" and patient.effort == ""  # none sent unless set

    groq = make_consultant(ConsultConfig.from_env({**SECRETS, "CURELAB_CONSULT_PROVIDER": "custom",
                                                   "CURELAB_CONSULT_MODEL": "llama-x"}))
    assert str(groq.client.base_url).startswith("https://api.groq.com/openai/v1") and groq.client.api_key == "gsk-secret"
    assert groq.vendor == "Groq"
    with pytest.raises(ConsultError, match="CURELAB_CONSULT_MODEL"):
        make_consultant(ConsultConfig.from_env({"CURELAB_CONSULT_BASE_URL": "http://localhost:11434/v1"}))
    monkeypatch.delenv("CURELAB_CONSULT_API_KEY")
    ollama = make_consultant(ConsultConfig.from_env({"CURELAB_CONSULT_BASE_URL": "http://localhost:11434/v1",
                                                     "CURELAB_CONSULT_MODEL": "llama3"}))
    assert ollama.client.api_key == "none"  # local servers need no key

    plan = make_consultant(ConsultConfig.from_env({"CLAUDE_CODE_OAUTH_TOKEN": "t"}), "bedside")
    assert isinstance(plan, ClaudePlanConsultant) and plan.model is None and plan.effort == "low"


def test_each_chat_has_its_own_model_and_effort(monkeypatch):
    env = {"ANTHROPIC_API_KEY": "k", "CURELAB_BEDSIDE_MODEL": "claude-haiku-4-5-20251001",
           "CURELAB_BEDSIDE_EFFORT": "High", "CURELAB_CONSULT_EFFORT": " max "}
    config = ConsultConfig.from_env(env)
    doctor, patient = make_consultant(config), make_consultant(config, "bedside")
    assert (doctor.model, doctor.effort) == ("claude-opus-5-5", "max")
    assert (patient.model, patient.effort) == ("claude-haiku-4-5-20251001", "high")
    public = config.public()
    assert (public["effort"], public["bedside_effort"]) == ("max", "high")
    # Claude's defaults: the doctor thinks harder than the patient
    defaults = ConsultConfig.from_env({"CLAUDE_CODE_OAUTH_TOKEN": "t"}).public()
    assert (defaults["effort"], defaults["bedside_effort"]) == ("medium", "low")
    # other services: nothing unless set
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    assert ConsultConfig.from_env({"OPENAI_API_KEY": "sk-x"}).public()["effort"] == ""
    chosen = ConsultConfig.from_env({"OPENAI_API_KEY": "sk-x", "CURELAB_BEDSIDE_EFFORT": "minimal"})
    assert make_consultant(chosen, "bedside").effort == "minimal" and make_consultant(chosen).effort == ""


def replying(record, *pieces):
    """A stand-in for chat.completions.create that streams ``pieces``."""
    from types import SimpleNamespace

    async def chunks():
        for piece in pieces:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=piece, refusal=None))])

    async def create(**kwargs):
        record.append(kwargs)
        return chunks()

    return create


def test_reasoning_effort_is_sent_only_when_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    for env, expected in (({}, None), ({"CURELAB_CONSULT_EFFORT": "high"}, "high")):
        consultant = make_consultant(ConsultConfig.from_env({"OPENAI_API_KEY": "sk-x", **env}))
        calls: list[dict] = []
        consultant.client.chat.completions.create = replying(calls, "Hel", "lo")
        assert collect(consultant) == ["Hel", "lo"]
        assert calls[0].get("reasoning_effort") == expected and calls[0]["stream"] is True


# --------------------------------------------------------------------------- #
# OpenAI-compatible services
# --------------------------------------------------------------------------- #


def failing(exc):
    async def create(**kwargs):
        raise exc

    return create


def test_openai_compatible_errors_name_the_service(monkeypatch):
    with pytest.raises(ConsultError, match="GEMINI_API_KEY"):  # no key: a message, not a crash
        make_consultant(ConsultConfig(provider="gemini", model="gemini-flash-latest"))
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret")
    gemini = make_consultant(ConsultConfig(provider="gemini", model="gemini-flash-latest"))
    request = httpx.Request("POST", GEMINI_BASE_URL + "chat/completions")
    limited = openai.RateLimitError("quota", response=httpx.Response(429, request=request), body=None)
    gemini.client.chat.completions.create = failing(limited)
    with pytest.raises(ConsultError) as err:
        collect(gemini)
    assert "Google is rate-limiting" in str(err.value) and "gemini-flash-lite-latest" in str(err.value)
    denied = openai.AuthenticationError("bad key", response=httpx.Response(401, request=request), body=None)
    gemini.client.chat.completions.create = failing(denied)
    with pytest.raises(ConsultError, match="GEMINI_API_KEY"):
        collect(gemini)
    # Gemini answers a bad key with 400 and a list-shaped body
    bad_key = openai.BadRequestError("Error code: 400", response=httpx.Response(400, request=request),
                                     body=[{"error": {"code": 400, "message": "Please pass a valid API key"}}])
    gemini.client.chat.completions.create = failing(bad_key)
    with pytest.raises(ConsultError, match="Google rejected the key"):
        collect(gemini)
    region = openai.PermissionDeniedError("Error code: 403", response=httpx.Response(403, request=request),
                                          body={"error": {"message": "User location is not supported"}})
    gemini.client.chat.completions.create = failing(region)
    with pytest.raises(ConsultError, match="Google refused: User location is not supported"):
        collect(gemini)
    gemini.client.chat.completions.create = failing(openai.APIConnectionError(request=request))
    with pytest.raises(ConsultError, match="Can't reach Google"):
        collect(gemini)


# --------------------------------------------------------------------------- #
# Claude through the learner's plan
# --------------------------------------------------------------------------- #


def delta(text, kind="text_delta"):
    key = "text" if kind == "text_delta" else "thinking"
    return StreamEvent(uuid="u", session_id="s", event={"type": "content_block_delta", "index": 0,
                                                        "delta": {"type": kind, key: text}})


def result(is_error=False, text="done"):
    return ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=is_error, num_turns=1,
                         session_id="s", result=text)


class FakeQuery:
    """Replays SDK messages and records how it was called and closed."""

    def __init__(self, *replies):
        self.replies = replies
        self.calls = []
        self.closed = False

    def __call__(self, *, prompt, options):
        self.calls.append((prompt, options))
        return self._run()

    async def _run(self):
        try:
            for reply in self.replies:
                yield reply
        finally:
            self.closed = True


def plan_with(*replies):
    consultant = ClaudePlanConsultant("", effort="low")
    consultant._query = FakeQuery(*replies)
    return consultant


def test_plan_streams_the_answer_with_no_tools_and_only_the_plan():
    answer = AssistantMessage(content=[TextBlock(text="Hello there.")], model="claude")
    consultant = plan_with(delta("hmm", "thinking_delta"), delta("Hello "), delta("there."), answer, result())
    assert collect(consultant, system="You are Walter.") == ["Hello ", "there."]  # not repeated at the end
    prompt, options = consultant._query.calls[0]
    assert prompt == "hi"
    assert options.system_prompt == "You are Walter." and options.tools == [] and options.max_turns == 1
    assert options.setting_sources == [] and options.effort == "low" and options.model is None
    assert options.include_partial_messages and "no-session-persistence" in options.extra_args
    # an API key configured alongside must not take over from the plan
    assert options.env["ANTHROPIC_API_KEY"] == "" and options.env["ANTHROPIC_AUTH_TOKEN"] == ""


def test_plan_falls_back_to_the_whole_message_without_stream_events():
    answer = AssistantMessage(content=[TextBlock(text="All at once.")], model="claude")
    assert collect(plan_with(answer, result())) == ["All at once."]


def test_plan_errors_are_explained_not_shown_as_answers():
    for kind, expected in (("authentication_failed", "claude setup-token"), ("rate_limit", "usage limit"),
                           ("billing_error", "billing")):
        failure = AssistantMessage(content=[TextBlock(text="Failed to authenticate. API Error: 401")],
                                   model="<synthetic>", error=kind)
        consultant = plan_with(failure, result(is_error=True))
        with pytest.raises(ConsultError, match=expected):
            collect(consultant)
        assert consultant._query.closed  # the CLI is shut down
    declined = AssistantMessage(content=[TextBlock(text="")], model="claude", stop_reason="refusal")
    with pytest.raises(ConsultError, match="declined"):
        collect(plan_with(declined))


def test_plan_prompt_carries_the_earlier_turns():
    messages = [
        {"role": "user", "content": "Bedside chart...\n\nThe doctor says:\nHow are you?"},
        {"role": "assistant", "content": "Tired, doctor."},
        {"role": "user", "content": "Did you sleep?"},
    ]
    prompt = plan_prompt(messages)
    assert prompt.index("How are you?") < prompt.index("Tired, doctor.") < prompt.index("Did you sleep?")
    assert "<assistant>\nTired, doctor.\n</assistant>" in prompt and prompt.endswith("Did you sleep?")
