"""Optional "consult another doctor" chat: an LLM colleague the learner can
ask anything at any point, with the current mission as context.

It is off unless an API key is configured (``OPENAI_API_KEY`` for ChatGPT or
``ANTHROPIC_API_KEY`` for Claude). The key only lives in this process; the
browser learns which provider and model are active, nothing else. What is
sent with each question is built by :func:`build_context` and never includes
a mission's reference solution, hidden check, expected values or notes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Mapping, Optional, Protocol

DEFAULT_MODELS = {"openai": "gpt-6-astra", "anthropic": "claude-opus-5-5", "fake": "echo"}
PROVIDER_LABELS = {"openai": "ChatGPT", "anthropic": "Claude", "fake": "Echo (test)"}
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
    provider: Optional[str] = None  # None: consulting is off
    model: str = ""

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "ConsultConfig":
        """Pick the provider from the configured keys.

        ``CURELAB_CONSULT_PROVIDER`` (openai / anthropic) decides when both
        keys are set; without it, an OpenAI key wins. ``fake`` is a
        network-free echo used by the tests.
        """
        keys = {
            "openai": bool(env.get("OPENAI_API_KEY", "").strip()),
            "anthropic": bool(env.get("ANTHROPIC_API_KEY", "").strip()),
        }
        wanted = env.get("CURELAB_CONSULT_PROVIDER", "").strip().lower()
        if wanted == "fake":
            provider: Optional[str] = "fake"
        elif wanted in keys:
            provider = wanted if keys[wanted] else None
        elif keys["openai"]:
            provider = "openai"
        elif keys["anthropic"]:
            provider = "anthropic"
        else:
            provider = None
        model = env.get("CURELAB_CONSULT_MODEL", "").strip() or DEFAULT_MODELS.get(provider or "", "")
        return cls(provider=provider, model=model if provider else "")

    def public(self) -> dict[str, Any]:
        """What the browser may know: never the key."""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "label": PROVIDER_LABELS.get(self.provider or "", ""),
            "model": self.model,
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
            raise ConsultError("The consulting doctor declined to answer that. Try rephrasing the question.")
        if final.stop_reason == "max_tokens":
            yield "\n\n*(The answer was cut off at the length limit.)*"


class OpenAIConsultant:
    """ChatGPT via the official ``openai`` SDK (reads ``OPENAI_API_KEY``)."""

    def __init__(self, model: str, effort: str = "medium"):
        import openai

        self._sdk = openai
        self.client = openai.AsyncOpenAI()
        self.model = model  # effort is not passed on: ChatGPT uses the model's default

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
                    if delta.refusal:
                        refused = True
                    if delta.content:
                        yield delta.content
        except sdk.AuthenticationError:
            raise ConsultError("OpenAI rejected the API key. Check OPENAI_API_KEY in your .env file.")
        except sdk.PermissionDeniedError:
            raise ConsultError("This OpenAI API key isn't allowed to use that model.")
        except sdk.NotFoundError:
            raise ConsultError(f"Model {self.model} isn't available to this key. Set CURELAB_CONSULT_MODEL.")
        except sdk.RateLimitError:
            raise ConsultError("OpenAI is rate-limiting this key (or it has no credit left). Wait and ask again.")
        except sdk.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ConsultError("OpenAI's servers had a problem. Try again in a moment.")
            raise ConsultError(f"ChatGPT couldn't answer: {exc.message}")
        except sdk.APIConnectionError:
            raise ConsultError("Can't reach OpenAI. Is this computer online?")
        if refused:
            raise ConsultError("The consulting doctor declined to answer that. Try rephrasing the question.")


def make_consultant(config: ConsultConfig, effort: str = "medium") -> Consultant:
    """``effort`` sets Claude's thinking effort; short chats (the bedside) use low."""
    if config.provider == "anthropic":
        return AnthropicConsultant(config.model, effort)
    if config.provider == "openai":
        return OpenAIConsultant(config.model, effort)
    if config.provider == "fake":
        return EchoConsultant(config.model, effort)
    raise ConsultError("Consulting is off: add OPENAI_API_KEY or ANTHROPIC_API_KEY to your .env file.")


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
