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
    return sum(1 for n in notebook.notes if word_count(n.body) >= min_words)


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
            lines += [
                f"<sub>Source: {src.vignette} — “{src.section}” "
                f"([site]({pack.source_pin.site_url(src.vignette)}), "
                f"[pinned {pack.source_pin.ref}]({pack.source_pin.blob_url(src.vignette)}))</sub>",
                "",
            ]
    if read is not None:
        lines += [f"*{'✓ Read' if read else 'Not yet read'}*", ""]
    return "\n".join(lines)


def render_note_markdown(note: Note) -> str:
    body = note.body.rstrip() or "*(empty page)*"
    return f"## {note.title}\n\n*Written {note.created[:10]} · updated {note.updated[:10]}*\n\n{body}\n"


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
