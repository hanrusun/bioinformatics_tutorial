"""Optional chats with a chatbot: "consult another doctor" (an LLM colleague
the learner can ask anything at any point, with the current mission as
context) and, sharing the same setup, the bedside chat with the patient
(:mod:`curelab.bedside`).

They are off until one of these is configured (see :meth:`ConsultConfig.from_env`):

- ``OPENAI_API_KEY``: ChatGPT, billed per use by OpenAI
- ``ANTHROPIC_API_KEY``: Claude, billed per use by Anthropic
- ``CLAUDE_CODE_OAUTH_TOKEN``: Claude through the learner's own Claude plan
  (Pro, Max, Team), a token made with ``claude setup-token``
- ``GEMINI_API_KEY``: Gemini, which has a free tier
- ``CURELAB_CONSULT_BASE_URL``: any other OpenAI-compatible service (Groq,
  OpenRouter, GitHub Models, a local Ollama), with ``CURELAB_CONSULT_MODEL``

Keys and tokens only live in this process; the browser learns which provider
and models are active, nothing else. What is sent with each question is built
by :func:`build_context` and never includes a mission's reference solution,
hidden check, expected values or notes.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from dataclasses import dataclass
from typing import Any, AsyncIterator, Mapping, Optional, Protocol
from urllib.parse import urlparse

# The credential that switches each provider on, in the order they are picked
# when CURELAB_CONSULT_PROVIDER doesn't choose one.
PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude-plan": "CLAUDE_CODE_OAUTH_TOKEN",
    "gemini": "GEMINI_API_KEY",
    "custom": "CURELAB_CONSULT_BASE_URL",
}
# "" for claude-plan: the plan's default model; "" for custom: must be set.
DEFAULT_MODELS = {
    "openai": "gpt-6-astra",
    "anthropic": "claude-opus-5-5",
    "claude-plan": "",
    "gemini": "gemini-flash-latest",
    "custom": "",
    "fake": "echo",
}
# The patient's small talk can use a lighter model. On Gemini's free tier,
# Flash-Lite also has a much larger daily quota than Flash.
BEDSIDE_MODELS = {"gemini": "gemini-flash-lite-latest"}
PROVIDER_LABELS = {
    "openai": "ChatGPT",
    "anthropic": "Claude",
    "claude-plan": "Claude (your plan)",
    "gemini": "Gemini",
    "fake": "Echo (test)",
}
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Friendly names for the OpenAI-compatible services people are likely to use.
KNOWN_HOSTS = {
    "api.groq.com": "Groq",
    "openrouter.ai": "OpenRouter",
    "models.github.ai": "GitHub Models",
    "models.inference.ai.azure.com": "GitHub Models",
    "host.docker.internal": "Ollama",
    "localhost": "Ollama",
    "127.0.0.1": "Ollama",
}
# Earlier turns resent with each question (user/assistant pairs, so even).
HISTORY_LIMIT = 20
# Caps on what is copied from the editor and the console into a question.
MAX_CODE_CHARS = 12_000
MAX_ERROR_CHARS = 4_000

SYSTEM_PROMPT = """\
You are a senior physician-scientist and bioinformatician on the ward in Cure \
Lab, a game in which a learner treats a fictional patient by working through \
single-cell analysis missions in R. The missions follow the official Seurat \
and Signac vignettes, pinned to the versions installed in the learner's lab. \
The learner has asked to consult you, the way a junior doctor pages a more \
experienced colleague, and they may do so at any point, not only after a \
mistake.

Answer whatever they ask: single-cell and chromatin analysis, R, statistics \
and the mathematics behind the methods (for example how UMAP, SCTransform or \
weighted nearest neighbors work), biology, and other tools. Questions do not \
have to be about the current mission.

Each question comes with a "Game context" block: the mission they have open \
(its briefing and task, and the vignette section it follows), which missions \
they have finished, and often their current code and last error. Use it to \
make your answer specific. For a mission they have open and have not \
finished, act as a coach: explain the concepts, what their error means and \
where their code goes wrong, and which functions and arguments matter, and \
use small examples on other data when that helps. Do not write out the \
complete code that solves that mission's task; if they ask for it, tell them \
the in-game hints reveal the vignette's code tier by tier. Missions they have \
already finished can be discussed openly, including their code.

Refer to the pinned vignettes when you describe what a function does, and say \
so when you are unsure or when the behaviour depends on the package version. \
The patients are fictional; do not give medical advice about real people. \
Keep answers focused and easy to read: short paragraphs, code in fenced \
blocks, lists where they help.\
"""


class ConsultError(Exception):
    """A failure to show the learner as-is (bad key, offline, declined, ...)."""


@dataclass(frozen=True)
class ConsultConfig:
    provider: Optional[str] = None  # None: the chats are off
    model: str = ""  # consult another doctor
    bedside_model: str = ""  # talk to the patient
    base_url: str = ""  # custom provider only

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "ConsultConfig":
        """Pick the provider from the configured credentials.

        ``CURELAB_CONSULT_PROVIDER`` (openai / anthropic / claude-plan / gemini
        / custom) decides when several are set; without it, the first one in
        :data:`PROVIDER_KEYS` wins. ``fake`` is a network-free echo used by the
        tests. ``CURELAB_CONSULT_MODEL`` and ``CURELAB_BEDSIDE_MODEL`` override
        the doctor's and the patient's model.
        """
        have = {p: bool(env.get(k, "").strip()) for p, k in PROVIDER_KEYS.items()}
        wanted = env.get("CURELAB_CONSULT_PROVIDER", "").strip().lower()
        if wanted == "fake":
            provider: Optional[str] = "fake"
        elif wanted in have:
            provider = wanted if have[wanted] else None
        else:
            provider = next((p for p, ok in have.items() if ok), None)
        if provider is None:
            return cls()
        model = env.get("CURELAB_CONSULT_MODEL", "").strip() or DEFAULT_MODELS.get(provider, "")
        bedside = env.get("CURELAB_BEDSIDE_MODEL", "").strip() or BEDSIDE_MODELS.get(provider, "") or model
        base_url = env.get("CURELAB_CONSULT_BASE_URL", "").strip() if provider == "custom" else ""
        return cls(provider=provider, model=model, bedside_model=bedside, base_url=base_url)

    @property
    def patient_model(self) -> str:
        """The bedside chat's model (the doctor's unless set apart)."""
        return self.bedside_model or self.model

    @property
    def label(self) -> str:
        if self.provider == "custom":
            host = urlparse(self.base_url).hostname or self.base_url
            return KNOWN_HOSTS.get(host, host)
        return PROVIDER_LABELS.get(self.provider or "", "")

    def public(self) -> dict[str, Any]:
        """What the browser may know: never a key or token."""
        default = "your plan's default model" if self.provider == "claude-plan" else ""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "label": self.label,
            "model": self.model or default,
            "bedside_model": self.patient_model or default,
        }


# --------------------------------------------------------------------------- #
# Context
# --------------------------------------------------------------------------- #


def _tail(text: str, limit: int) -> str:
    text = text.rstrip()
    if len(text) <= limit:
        return text
    return f"(showing the last {limit} of {len(text)} characters)\n" + text[-limit:]


def build_context(
    *,
    tool: str,
    campaign_title: str,
    finished: list[str],
    mission: Optional[dict[str, Any]] = None,
    code: str = "",
    last_error: str = "",
    include_code: bool = True,
    language: str = "r",
) -> str:
    """The "Game context" block sent with a question.

    ``mission`` holds only learner-facing fields: number, title, finished,
    briefing, task and source (vignette, section, url).
    """
    lines = ["Game context", f"Lab: {tool}", f"Campaign: {campaign_title}"]
    lines.append("Finished missions: " + ("; ".join(finished) if finished else "none yet"))
    if mission is None:
        lines.append("The learner has no mission open right now.")
        return "\n".join(lines)
    state = "finished" if mission["finished"] else "open, not finished yet"
    lines += [f"Mission open: {mission['number']}. {mission['title']} ({state})", "", "Briefing:", mission["briefing"].strip()]
    if mission["task"]:
        lines += ["", "Task:"] + [f"- {t}" for t in mission["task"]]
    src = mission.get("source")
    if src:
        lines += ["", f"Follows: {src['vignette']}, section \"{src['section']}\" ({src['url']})"]
    if not include_code:
        lines += ["", "The learner chose not to share their code or errors."]
        return "\n".join(lines)
    if code.strip():
        lines += ["", "Learner's current code:", f"```{language}", _tail(code, MAX_CODE_CHARS), "```"]
    else:
        lines += ["", "Learner's current code: (empty)"]
    if last_error.strip():
        lines += ["", "Last error:", "```", _tail(last_error, MAX_ERROR_CHARS), "```"]
    return "\n".join(lines)


def question_prompt(context: str, question: str) -> str:
    return f"{context}\n\nQuestion:\n{question.strip()}"


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #


class Consultant(Protocol):
    def stream(self, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...


class EchoConsultant:
    """Network-free stand-in for tests: repeats the question in a few pieces."""

    def __init__(self, model: str, effort: str = "medium"):
        self.model = model

    async def stream(self, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        question = messages[-1]["content"]
        for marker in ("Question:\n", "The doctor says:\n"):  # consult / bedside prompts
            question = question.rsplit(marker, 1)[-1]
        text = f"Echo: you said “{question.strip()}”. ({len(messages) // 2} earlier turns)"
        for i in range(0, len(text), 16):
            yield text[i : i + 16]


class AnthropicConsultant:
    """Claude via the official ``anthropic`` SDK (reads ``ANTHROPIC_API_KEY``)."""

    def __init__(self, model: str, effort: str = "medium"):
        import anthropic

        self._sdk = anthropic
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort

    async def stream(self, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        sdk = self._sdk
        try:
            async with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=64000,
                system=system,
                messages=messages,  # type: ignore[arg-type]
                output_config={"effort": self.effort},
                cache_control={"type": "ephemeral"},  # caches the growing conversation
                # on a policy decline, the API re-runs the request on a fallback model
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except sdk.AuthenticationError:
            raise ConsultError("Claude rejected the API key. Check ANTHROPIC_API_KEY in your .env file.")
        except sdk.PermissionDeniedError:
            raise ConsultError("This Anthropic API key isn't allowed to use that model.")
        except sdk.NotFoundError:
            raise ConsultError(f"Model {self.model} isn't available to this key. Set CURELAB_CONSULT_MODEL.")
        except sdk.RateLimitError:
            raise ConsultError("Claude is rate-limiting this key. Wait a minute and ask again.")
        except sdk.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ConsultError("Anthropic's servers had a problem. Try again in a moment.")
            raise ConsultError(f"Claude couldn't answer: {exc.message}")
        except sdk.APIConnectionError:
            raise ConsultError("Can't reach Claude. Is this computer online?")
        if final.stop_reason == "refusal":
            raise ConsultError("The chatbot declined to answer that. Try rephrasing it.")
        if final.stop_reason == "max_tokens":
            yield "\n\n*(The answer was cut off at the length limit.)*"


class OpenAIConsultant:
    """ChatGPT via the official ``openai`` SDK, or any service that speaks the
    same chat API (Gemini, Groq, OpenRouter, GitHub Models, Ollama) when given
    its ``base_url``.

    ``label`` and ``key_env`` name the service and its credential in error
    messages. ``effort`` is not passed on: these services differ in how (and
    whether) they accept it, so each model runs at its own default.
    """

    def __init__(
        self,
        model: str,
        effort: str = "medium",
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        label: str = "ChatGPT",
        vendor: str = "OpenAI",
        key_env: str = "OPENAI_API_KEY",
        rate_hint: str = "",
    ):
        import openai

        self._sdk = openai
        try:  # api_key None: the SDK reads OPENAI_API_KEY
            self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        except openai.OpenAIError:
            raise ConsultError(f"{vendor} needs a key: set {key_env} in your .env file.")
        self.model = model
        self.label, self.vendor, self.key_env, self.rate_hint = label, vendor, key_env, rate_hint

    async def stream(self, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        sdk = self._sdk
        refused = False
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, *messages],  # type: ignore[list-item]
                stream=True,
            )
            async for chunk in stream:
                for choice in chunk.choices:
                    delta = choice.delta
                    if delta is None:
                        continue
                    if getattr(delta, "refusal", None):
                        refused = True
                    if delta.content:
                        yield delta.content
        except sdk.AuthenticationError:
            raise ConsultError(f"{self.vendor} rejected the key. Check {self.key_env} in your .env file.")
        except sdk.PermissionDeniedError as exc:
            raise ConsultError(f"{self.vendor} refused: {_error_detail(exc)}")
        except sdk.NotFoundError:
            raise ConsultError(f"Model {self.model} isn't available here. Set CURELAB_CONSULT_MODEL.")
        except sdk.RateLimitError:
            raise ConsultError(
                f"{self.vendor} is rate-limiting this key (or it has no credit left). Wait and ask again."
                + (f" {self.rate_hint}" if self.rate_hint else "")
            )
        except sdk.APIStatusError as exc:
            detail = _error_detail(exc)
            if exc.status_code >= 500:
                raise ConsultError(f"{self.vendor}'s servers had a problem. Try again in a moment.")
            if "api key" in detail.lower():  # Gemini answers a bad key with 400, not 401
                raise ConsultError(f"{self.vendor} rejected the key. Check {self.key_env} in your .env file.")
            raise ConsultError(f"{self.label} couldn't answer: {detail}")
        except sdk.APIConnectionError:
            raise ConsultError(f"Can't reach {self.vendor}. Is this computer online?")
        if refused:
            raise ConsultError("The chatbot declined to answer that. Try rephrasing it.")


def _error_detail(exc: Any) -> str:
    """The service's own message from an API error, e.g. Gemini's
    ``[{"error": {"message": ...}}]`` or OpenAI's ``{"error": {"message": ...}}``."""
    body = exc.body[0] if isinstance(exc.body, list) and exc.body else exc.body
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict) and inner.get("message"):
            return str(inner["message"])
    return str(exc.message)


def plan_prompt(messages: list[dict[str, str]]) -> str:
    """The conversation as one message: the Claude CLI takes a single prompt
    per call, so earlier turns come along as context."""
    *earlier, last = messages
    if not earlier:
        return last["content"]
    parts = ["(The conversation so far, for context.)"]
    parts += [f"<{m['role']}>\n{m['content']}\n</{m['role']}>" for m in earlier]
    parts.append("(Reply to this latest message.)\n\n" + last["content"])
    return "\n\n".join(parts)


class ClaudePlanConsultant:
    """Claude through the learner's own Claude plan (Pro, Max, Team).

    The Claude Agent SDK runs the Claude Code CLI it bundles, signed in with
    the token from ``claude setup-token`` (``CLAUDE_CODE_OAUTH_TOKEN``), so the
    chats count against the plan's usage limits instead of an API bill. Each
    question is one answer with no tools, no files and no saved session.
    """

    # the plan's own error kinds (claude_agent_sdk.AssistantMessageError)
    ERRORS = {
        "authentication_failed": (
            "Your Claude plan didn't accept the token. Run `claude setup-token` again and put the new "
            "token in CLAUDE_CODE_OAUTH_TOKEN in your .env file."
        ),
        "rate_limit": (
            "You've reached your Claude plan's usage limit for now. It resets after a while; the rest of "
            "the game keeps working."
        ),
        "billing_error": "Claude reports a billing problem with this account. Check your plan at claude.ai.",
        "server_error": "Anthropic's servers had a problem. Try again in a moment.",
    }

    def __init__(self, model: str, effort: str = "medium"):
        import claude_agent_sdk

        self._sdk = claude_agent_sdk
        self._query = claude_agent_sdk.query
        self.model = model or None  # None: the plan's default model
        self.effort = effort
        self.cwd = tempfile.mkdtemp(prefix="curelab-chat-")  # an empty folder: nothing to read

    def options(self, system: str) -> Any:
        return self._sdk.ClaudeAgentOptions(
            system_prompt=system,
            model=self.model,
            effort=self.effort,
            tools=[],
            max_turns=1,
            setting_sources=[],
            include_partial_messages=True,
            cwd=self.cwd,
            extra_args={"no-session-persistence": None},
            env={
                # always the plan, even when an API key is configured as well
                "ANTHROPIC_API_KEY": "",
                "ANTHROPIC_AUTH_TOKEN": "",
                "DISABLE_AUTOUPDATER": "1",
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "CLAUDE_AGENT_SDK_CLIENT_APP": "curelab",
            },
        )

    async def stream(self, system: str, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        sdk = self._sdk
        streamed = False
        try:
            async with contextlib.aclosing(self._query(prompt=plan_prompt(messages), options=self.options(system))) as replies:
                async for msg in replies:
                    if isinstance(msg, sdk.StreamEvent):
                        event = msg.event
                        delta = event.get("delta") or {}
                        if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                            streamed = True
                            yield delta.get("text", "")
                    elif isinstance(msg, sdk.AssistantMessage):
                        text = "".join(b.text for b in msg.content if isinstance(b, sdk.TextBlock))
                        if msg.error:  # the text is the CLI's error, not an answer
                            raise ConsultError(self.ERRORS.get(msg.error, f"Claude couldn't answer: {text}"))
                        if msg.stop_reason == "refusal":
                            raise ConsultError("The chatbot declined to answer that. Try rephrasing it.")
                        if not streamed and text:
                            streamed = True
                            yield text
                    elif isinstance(msg, sdk.ResultMessage) and msg.is_error:
                        raise ConsultError(f"Claude couldn't answer: {msg.result or msg.subtype}")
        except ConsultError:
            raise
        except sdk.CLINotFoundError:
            raise ConsultError("The Claude CLI that comes with the game is missing. Rebuild the image.")
        except sdk.ClaudeSDKError as exc:
            raise ConsultError(f"Claude couldn't answer: {exc}")


def make_consultant(config: ConsultConfig, effort: str = "medium", model: Optional[str] = None) -> Consultant:
    """``effort`` sets Claude's thinking effort (short chats like the bedside
    use low); ``model`` overrides the doctor's model (the patient's)."""
    model = config.model if model is None else model
    if config.provider == "anthropic":
        return AnthropicConsultant(model, effort)
    if config.provider == "openai":
        return OpenAIConsultant(model, effort)
    if config.provider == "claude-plan":
        return ClaudePlanConsultant(model, effort)
    if config.provider == "gemini":
        return OpenAIConsultant(
            model,
            effort,
            base_url=GEMINI_BASE_URL,
            api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
            label="Gemini",
            vendor="Google",
            key_env="GEMINI_API_KEY",
            rate_hint=(
                "Gemini's free tier allows a few requests a minute and a daily quota per model; "
                "gemini-flash-lite-latest has the largest (set it in CURELAB_CONSULT_MODEL)."
            ),
        )
    if config.provider == "custom":
        if not model:
            raise ConsultError("Set CURELAB_CONSULT_MODEL to the model name your provider uses.")
        return OpenAIConsultant(
            model,
            effort,
            base_url=config.base_url,
            # local servers such as Ollama need no key, but the SDK wants one
            api_key=os.environ.get("CURELAB_CONSULT_API_KEY", "").strip() or "none",
            label=config.label,
            vendor=config.label,
            key_env="CURELAB_CONSULT_API_KEY",
        )
    if config.provider == "fake":
        return EchoConsultant(model, effort)
    raise ConsultError("The chats are off: add a key to your .env file (see the README).")


def transcript_markdown(
    turns: list[dict[str, Any]], speaker: str, label: str, mission_titles: Mapping[str, str]
) -> str:
    """A saved conversation as notebook Markdown (question/answer pairs).

    ``speaker`` answers (the consulting doctor, or the patient); ``label``
    names the chatbot behind them, if shown."""
    out: list[str] = []
    for turn in turns:
        if turn["role"] == "user":
            where = mission_titles.get(turn.get("mission_id") or "", "")
            head = f"**You** (day {turn['day']}{', ' + where if where else ''}):"
            out += [head, "", turn["text"].strip(), ""]
        else:
            out += [f"**{speaker}**{f' ({label})' if label else ''}:", "", turn["text"].strip(), ""]
    return "\n".join(out).rstrip() + "\n"
