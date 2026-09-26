"""Content schemas and loaders for packs, campaigns, missions, quizzes,
notebook pages and illnesses.

Layout of a pack directory::

    packs/<pack>/pack.yaml
    packs/<pack>/campaigns/<campaign>/campaign.yaml
    packs/<pack>/campaigns/<campaign>/missions/NN_<slug>.yaml   (sorted by file name)
    packs/<pack>/campaigns/<campaign>/quizzes.yaml
    packs/<pack>/campaigns/<campaign>/notebook/NN_<slug>.yaml   (sorted by file name)

Illnesses live in a separate, tool-agnostic directory: ``illnesses/<id>.yaml``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContentError(ValueError):
    """Raised when pack or illness content is malformed or inconsistent."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #


class SourcePin(_Model):
    """Where the tutorial content comes from, pinned to an exact revision."""

    repo: str  # e.g. satijalab/seurat
    ref: str  # e.g. v5.5.1
    path: str = ""  # directory inside the repo holding the source documents
    site: str = ""  # rendered site base, e.g. https://satijalab.org/seurat/articles/

    def raw_url(self, document: str) -> str:
        prefix = f"{self.path.strip('/')}/" if self.path else ""
        return f"https://raw.githubusercontent.com/{self.repo}/{self.ref}/{prefix}{document}"

    def blob_url(self, document: str) -> str:
        prefix = f"{self.path.strip('/')}/" if self.path else ""
        return f"https://github.com/{self.repo}/blob/{self.ref}/{prefix}{document}"

    def site_url(self, document: str) -> str:
        if not self.site:
            return self.blob_url(document)
        stem = document.rsplit(".", 1)[0]
        return f"{self.site.rstrip('/')}/{stem}.html"


class Source(_Model):
    """A citation into a pinned source document.

    ``quote`` (when present) must appear verbatim in the document; this is
    enforced by ``tools/verify_sources.py``.
    """

    vignette: str
    section: str
    quote: Optional[str] = None


# --------------------------------------------------------------------------- #
# Missions, quizzes, notebook pages
# --------------------------------------------------------------------------- #


class DebugRule(_Model):
    pattern: str  # regular expression matched against the error text
    help: str


class WrongSolution(_Model):
    code: str
    why: str


class Mission(_Model):
    id: str
    title: str
    points: int = Field(ge=1, le=100)
    source: Source
    briefing: str
    task: list[str]
    starter_code: str = ""
    setup: str = ""
    solution: str
    check: str
    hints: list[str]
    debug: list[DebugRule] = []
    notebook_pages: list[str] = []
    # Objects saved into the checkpoint after the reference solution runs.
    state: list[str] = []
    # key -> expression (in the pack language) evaluated after the reference
    # solution at build time; results land in expected.json for the checks.
    expected: dict[str, str] = {}
    # Deliberately wrong code that the check must reject (tested at build time).
    wrong_solutions: list[WrongSolution] = []
    timeout: int = Field(default=900, ge=5)
    # Extra quotes/code that must be verified against the source (e.g. the
    # solution is verbatim vignette code).
    verbatim_solution: bool = True

    @field_validator("hints")
    @classmethod
    def _three_hints(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError("missions need exactly three hint tiers")
        return v


class Quiz(_Model):
    id: str
    after: str  # mission id that unlocks this quiz
    question: str
    choices: list[str]
    answer: int
    explanation: str
    source: Source
    points: int = 1

    @model_validator(mode="after")
    def _answer_in_range(self) -> "Quiz":
        if not 2 <= len(self.choices) <= 5:
            raise ValueError(f"quiz {self.id}: needs 2-5 choices")
        if not 0 <= self.answer < len(self.choices):
            raise ValueError(f"quiz {self.id}: answer index out of range")
        if len(set(self.choices)) != len(self.choices):
            raise ValueError(f"quiz {self.id}: duplicate choices")
        return self


class NotebookBlock(_Model):
    kind: Literal["text", "quote", "code"]
    text: str
    source: Optional[Source] = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        # YAML shorthand: {text: ...} | {quote: ..., source: ...} | {code: ..., source: ...}
        if isinstance(data, dict) and "kind" not in data:
            for kind in ("quote", "code", "text"):
                if kind in data:
                    out = {"kind": kind, "text": data[kind]}
                    if "source" in data:
                        out["source"] = data["source"]
                    extra = set(data) - {kind, "source"}
                    if extra:
                        raise ValueError(f"unexpected keys in notebook block: {sorted(extra)}")
                    return out
        return data

    @model_validator(mode="after")
    def _needs_source(self) -> "NotebookBlock":
        if self.kind in ("quote", "code") and self.source is None:
            raise ValueError("quote/code notebook blocks must cite a source")
        return self


class NotebookPage(_Model):
    id: str
    title: str
    rp: int = Field(default=1, ge=0, le=5)
    missions: list[str] = []
    blocks: list[NotebookBlock]


class Campaign(_Model):
    id: str
    title: str
    subtitle: str = ""
    illness: str
    order: int = 1
    unlock_after: Optional[str] = None
    summary: str = ""
    datasets: list[str] = []
    missions: list[Mission] = []
    quizzes: list[Quiz] = []
    notebook: list[NotebookPage] = []

    @property
    def total_points(self) -> int:
        return sum(m.points for m in self.missions) + sum(q.points for q in self.quizzes)

    def mission(self, mission_id: str) -> Mission:
        for m in self.missions:
            if m.id == mission_id:
                return m
        raise KeyError(mission_id)

    def quiz(self, quiz_id: str) -> Quiz:
        for q in self.quizzes:
            if q.id == quiz_id:
                return q
        raise KeyError(quiz_id)

    def page(self, page_id: str) -> NotebookPage:
        for p in self.notebook:
            if p.id == page_id:
                return p
        raise KeyError(page_id)

    def mission_index(self, mission_id: str) -> int:
        for i, m in enumerate(self.missions):
            if m.id == mission_id:
                return i
        raise KeyError(mission_id)


class Pack(_Model):
    id: str
    name: str
    tool: str
    tool_version: str
    language: str
    kernel: str
    editor_mode: str = "r"
    source_pin: SourcePin
    # Code run once in a fresh kernel before any mission setup. ``{pack_dir}``
    # is substituted with the absolute pack directory.
    init_code: str = ""
    # Template run before a mission's setup/check to tell helpers which
    # mission is active. ``{mission_id}`` is substituted.
    mission_prelude: str = ""
    debug: list[DebugRule] = []
    # pack.yaml lists campaign directory names under `campaigns:`; load_pack
    # moves them here and fills `campaigns` with the loaded Campaign objects.
    campaign_ids: list[str] = []
    campaigns: list[Campaign] = Field(default_factory=list, exclude=True)
    dir: Optional[Path] = Field(default=None, exclude=True)

    def campaign(self, campaign_id: str) -> Campaign:
        for c in self.campaigns:
            if c.id == campaign_id:
                return c
        raise KeyError(campaign_id)

    def render_init(self) -> str:
        return self.init_code.replace("{pack_dir}", str(self.dir))

    def render_prelude(self, mission_id: str) -> str:
        return self.mission_prelude.replace("{mission_id}", mission_id)


# --------------------------------------------------------------------------- #
# Illnesses and patients
# --------------------------------------------------------------------------- #

VITAL_KEYS = ("hr", "rr", "spo2", "sbp", "dbp", "temp")


class Vitals(_Model):
    hr: float  # heart rate, beats/min
    rr: float  # respiratory rate, breaths/min
    spo2: float  # oxygen saturation, %
    sbp: float  # systolic blood pressure, mmHg
    dbp: float  # diastolic blood pressure, mmHg
    temp: float  # body temperature, deg C


class Pronouns(_Model):
    subj: str
    obj: str
    poss: str


class Patient(_Model):
    id: str
    name: str
    first_name: str
    pronouns: Pronouns
    age: str
    sex: str
    background: str
    presenting: str
    companion: str = ""
    baseline_vitals: Vitals
    art: str  # key of the art set in web/src/art/


class Trait(_Model):
    id: str
    name: str
    category: Literal["symptom", "complication", "mutation", "resistance", "event"]
    tier: int = Field(ge=1, le=4)
    requires: list[str] = []
    # Traits that cannot co-occur with this one (e.g. mutually exclusive drivers).
    excludes: list[str] = []
    severity: tuple[float, float]
    vitals: dict[str, float] = {}
    overlay: Optional[str] = None
    note: str
    source: Optional[str] = None

    @property
    def is_event(self) -> bool:
        """A non-symptom "bad patient event" (e.g. the patient starts smoking)."""
        return self.category == "event"

    @property
    def neutral(self) -> bool:
        """Neutral events make a good story but don't change lethality."""
        return self.severity[1] == 0

    @model_validator(mode="after")
    def _check(self) -> "Trait":
        lo, hi = self.severity
        if not 0 <= lo <= hi:
            raise ValueError(f"trait {self.id}: severity must satisfy 0 <= lo <= hi")
        if hi == 0 and not self.is_event:
            raise ValueError(f"trait {self.id}: only patient events can be neutral (severity [0, 0])")
        if lo == 0 and hi > 0:
            raise ValueError(f"trait {self.id}: use [0, 0] for a neutral event, or a range above 0")
        bad = set(self.vitals) - set(VITAL_KEYS)
        if bad:
            raise ValueError(f"trait {self.id}: unknown vitals {sorted(bad)}")
        return self


class Illness(_Model):
    id: str
    name: str
    short: str
    blurb: str
    fictional_notice: str = ""
    patient: Patient
    admit_note: str
    stage_notes: dict[str, str] = {}
    progression_note: str
    cure_note: str
    loss_note: str
    traits: list[Trait]
    sources: list[str] = []

    @model_validator(mode="after")
    def _check_tree(self) -> "Illness":
        ids = [t.id for t in self.traits]
        if len(ids) != len(set(ids)):
            raise ValueError(f"illness {self.id}: duplicate trait ids")
        known = set(ids)
        for t in self.traits:
            missing = (set(t.requires) | set(t.excludes)) - known
            if missing:
                raise ValueError(f"trait {t.id} references unknown traits {sorted(missing)}")
        # cycle detection
        graph = {t.id: list(t.requires) for t in self.traits}
        state: dict[str, int] = {}

        def visit(node: str) -> None:
            if state.get(node) == 1:
                raise ValueError(f"illness {self.id}: trait prerequisites form a cycle at {node}")
            if state.get(node) == 2:
                return
            state[node] = 1
            for nxt in graph[node]:
                visit(nxt)
            state[node] = 2

        for node in graph:
            visit(node)
        if not any(not t.requires for t in self.traits):
            raise ValueError(f"illness {self.id}: needs at least one root trait")
        return self

    def trait(self, trait_id: str) -> Trait:
        for t in self.traits:
            if t.id == trait_id:
                return t
        raise KeyError(trait_id)

    def fill(self, template: str) -> str:
        """Substitute patient placeholders such as ``{name}``; other braces
        (e.g. R code in a briefing) are left untouched."""
        p = self.patient
        values = {
            "name": p.first_name,
            "full_name": p.name,
            "they": p.pronouns.subj,
            "them": p.pronouns.obj,
            "their": p.pronouns.poss,
            "They": p.pronouns.subj.capitalize(),
            "Their": p.pronouns.poss.capitalize(),
            "companion": p.companion,
        }
        return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), template)


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


def _read_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # pragma: no cover - message passthrough
        raise ContentError(f"{path}: invalid YAML: {exc}") from exc


def _parse(model: type[BaseModel], data: Any, where: Path) -> Any:
    try:
        return model.model_validate(data)
    except Exception as exc:
        raise ContentError(f"{where}: {exc}") from exc


def load_campaign(campaign_dir: Path) -> Campaign:
    data = _read_yaml(campaign_dir / "campaign.yaml") or {}
    missions = [
        _parse(Mission, _read_yaml(p), p) for p in sorted((campaign_dir / "missions").glob("*.yaml"))
    ]
    quizzes_path = campaign_dir / "quizzes.yaml"
    quizzes_raw = _read_yaml(quizzes_path) if quizzes_path.exists() else []
    quizzes = [_parse(Quiz, q, quizzes_path) for q in (quizzes_raw or [])]
    pages = [
        _parse(NotebookPage, _read_yaml(p), p)
        for p in sorted((campaign_dir / "notebook").glob("*.yaml"))
    ]
    campaign = _parse(Campaign, {**data, "missions": [], "quizzes": [], "notebook": []}, campaign_dir)
    campaign.missions = missions
    campaign.quizzes = quizzes
    campaign.notebook = pages
    validate_campaign(campaign)
    return campaign


def validate_campaign(c: Campaign) -> None:
    ids = [m.id for m in c.missions] + [q.id for q in c.quizzes] + [p.id for p in c.notebook]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ContentError(f"campaign {c.id}: duplicate ids {sorted(dupes)}")
    mission_ids = {m.id for m in c.missions}
    page_ids = {p.id for p in c.notebook}
    for q in c.quizzes:
        if q.after not in mission_ids:
            raise ContentError(f"quiz {q.id}: 'after' refers to unknown mission {q.after}")
    for p in c.notebook:
        unknown = set(p.missions) - mission_ids
        if unknown:
            raise ContentError(f"notebook page {p.id}: unknown missions {sorted(unknown)}")
    for m in c.missions:
        unknown = set(m.notebook_pages) - page_ids
        if unknown:
            raise ContentError(f"mission {m.id}: unknown notebook pages {sorted(unknown)}")


def load_pack(pack_dir: Path | str) -> Pack:
    pack_dir = Path(pack_dir).resolve()
    data = dict(_read_yaml(pack_dir / "pack.yaml") or {})
    data["campaign_ids"] = data.pop("campaigns", [])
    pack = _parse(Pack, data, pack_dir / "pack.yaml")
    pack.dir = pack_dir
    pack.campaigns = [load_campaign(pack_dir / "campaigns" / cid) for cid in pack.campaign_ids]
    known = {c.id for c in pack.campaigns}
    for c in pack.campaigns:
        if c.unlock_after and c.unlock_after not in known:
            raise ContentError(f"campaign {c.id}: unlock_after refers to unknown campaign")
    return pack


def load_illness(illness_dir: Path | str, illness_id: str) -> Illness:
    path = Path(illness_dir) / f"{illness_id}.yaml"
    if not path.exists():
        raise ContentError(f"illness file not found: {path}")
    illness = _parse(Illness, _read_yaml(path), path)
    if illness.id != illness_id:
        raise ContentError(f"{path}: id '{illness.id}' does not match file name")
    return illness


def load_illnesses_for(pack: Pack, illness_dir: Path | str) -> dict[str, Illness]:
    return {c.illness: load_illness(illness_dir, c.illness) for c in pack.campaigns}
