"""The lab notebook: preloaded source pages plus the learner's own notes."""

from __future__ import annotations

import datetime as _dt
import re
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .content import Campaign, Illness, NotebookPage, Pack

Scope = Literal["all", "mine"]


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class Note(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    title: str = "Untitled page"
    body: str = ""
    created: str = Field(default_factory=_now)
    updated: str = Field(default_factory=_now)
    # "consult": a saved conversation with the consulting doctor. It lives in
    # the notebook like any page but never earns research points.
    kind: Literal["note", "consult"] = "note"


class Notebook(BaseModel):
    notes: list[Note] = []

    def get(self, note_id: str) -> Note:
        for n in self.notes:
            if n.id == note_id:
                return n
        raise KeyError(note_id)


_HAS_ALNUM = re.compile(r"[A-Za-z0-9]")


def word_count(text: str) -> int:
    """Whitespace-separated tokens that contain at least one letter or digit."""
    return sum(1 for token in (text or "").split() if _HAS_ALNUM.search(token))


def qualifying_notes(notebook: Notebook, min_words: int) -> int:
    """Pages that earn research points: the learner's own, long enough."""
    return sum(1 for n in notebook.notes if n.kind == "note" and word_count(n.body) >= min_words)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def render_page_markdown(pack: Pack, page: NotebookPage, read: Optional[bool] = None) -> str:
    lines = [f"## {page.title}", ""]
    if page.missions:
        lines += [f"*Helps with:* {', '.join(page.missions)}", ""]
    for block in page.blocks:
        if block.kind == "text":
            lines += [block.text.strip(), ""]
        elif block.kind == "quote":
            quoted = "\n".join(f"> {ln}" if ln else ">" for ln in block.text.strip().splitlines())
            lines += [quoted, ""]
        else:
            lines += [f"```{pack.editor_mode}", block.text.rstrip(), "```", ""]
        if block.source is not None:
            src = block.source
            pin, document = pack.resolve_source(src.vignette)
            lines += [
                f"<sub>Source: {document} — “{src.section}” "
                f"([site]({pin.site_url(document)}), "
                f"[pinned {pin.repo}@{pin.ref}]({pin.blob_url(document)}))</sub>",
                "",
            ]
    if read is not None:
        lines += [f"*{'✓ Read' if read else 'Not yet read'}*", ""]
    return "\n".join(lines)


def render_note_markdown(note: Note) -> str:
    body = note.body.rstrip() or "*(empty page)*"
    what = "Consultation saved" if note.kind == "consult" else "Written"
    return f"## {note.title}\n\n*{what} {note.created[:10]} · updated {note.updated[:10]}*\n\n{body}\n"


_SCRIPT_EXT = {"r": "R", "python": "py"}


def script_filename(pack: Pack, campaign: Campaign) -> str:
    return f"curelab-{campaign.id}.{_SCRIPT_EXT.get(pack.language, 'txt')}"


def export_script(pack: Pack, campaign: Campaign, illness: Illness, game=None) -> str:
    """Every mission's description as comments, each followed by the code the
    learner submitted that passed (an R script for the R packs)."""
    rule = "# " + "-" * 76
    today = _dt.date.today().isoformat()
    out = [
        f"# Cure Lab — {campaign.title}",
        f"# {pack.name} {pack.tool_version} · patient: {illness.patient.name} ({illness.short}) · exported {today}",
        "#",
        "# Your passing code for each mission, in order, under the mission's",
        "# briefing and task. In the game every mission started from a saved",
        "# checkpoint of the vignette's own result, so each block assumes the",
        "# objects made by the missions before it, and data paths point into the",
        "# lab's Docker image.",
    ]
    if game is None:
        out += ["#", "# No game of this campaign is loaded, so there is no code to export."]
    for number, m in enumerate(campaign.missions, 1):
        progress = game.state.missions.get(m.id) if game is not None else None
        pin, document = pack.resolve_source(m.source.vignette)
        out += ["", "", rule, f"# Mission {number}: {m.title}  (+{m.points}% cure)"]
        out.append(f'# Follows: {document}, "{m.source.section}"')
        out.append(f"#   {pin.site_url(document)}")
        out.append("#")
        for line in illness.fill(m.briefing).strip().splitlines():
            out.append(f"# {line}".rstrip())
        if m.task:
            out += ["#", "# Task:"] + [f"#   - {t}" for t in m.task]
        out.append(rule)
        if progress is None or not progress.completed:
            out.append("# (not passed yet)")
        elif progress.passed_code is None:
            out.append("# (passed before the game started keeping your code)")
        else:
            out.append(progress.passed_code.rstrip())
    return "\n".join(out) + "\n"


def export_markdown(
    pack: Pack,
    campaign: Campaign,
    illness: Illness,
    notebook: Notebook,
    scope: Scope = "all",
    game=None,
) -> str:
    """Render the notebook as Markdown.

    ``scope="mine"`` exports only the learner's own pages; ``"all"`` adds the
    preloaded source pages (with citations) and a mission log.
    """
    today = _dt.date.today().isoformat()
    header = [
        f"# Cure Lab notebook — {campaign.title}",
        "",
        f"*{pack.name} {pack.tool_version} · patient: {illness.patient.name} ({illness.short}) · exported {today}*",
        "",
    ]
    mine = [render_note_markdown(n) for n in notebook.notes] or ["*No notes written yet.*\n"]
    if scope == "mine":
        return "\n".join(header + ["# My notes", ""] + mine)

    read = set(game.state.pages_read) if game is not None else set()
    out = header + ["# Reference pages", ""]
    for page in campaign.notebook:
        out.append(render_page_markdown(pack, page, read=page.id in read if game is not None else None))
    out += ["# My notes", ""] + mine
    if game is not None:
        out += ["# Mission log", "", "| Mission | Points | Status | Attempts | Hints |", "|---|---|---|---|---|"]
        for m in campaign.missions:
            p = game.state.missions.get(m.id)
            status = "✓ day %s" % p.completed_day if p and p.completed else game.mission_status(m.id)
            out.append(
                f"| {m.title} | {m.points}% | {status} | {p.attempts if p else 0} | {p.hints_bought if p else 0} |"
            )
        out += ["", "# Patient chart", ""]
        out += [f"- **Day {t.day}** — {t.text}" for t in game.state.timeline]
        out.append("")
    return "\n".join(out)
