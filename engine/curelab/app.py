"""HTTP API + static web UI."""

from __future__ import annotations

import asyncio
import os
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .balance import Balance, load_balance
from .content import Campaign, Illness, Pack, load_illnesses_for, load_pack
from .game import Game, RuleError
from .grader import Grader, debug_help
from .notebook import Note, _now, export_markdown, qualifying_notes, word_count
from .runner import KernelRunner
from .store import Profile, Store

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    pack_dir: Path
    illness_dir: Path
    data_dir: Path
    web_dir: Optional[Path] = None
    kernel: Optional[str] = None
    unlock_all: bool = False
    balance_path: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "Settings":
        pack_dir = Path(os.environ.get("CURELAB_PACK_DIR", REPO_ROOT / "packs" / "seurat"))
        web_default = REPO_ROOT / "web" / "dist"
        web_dir = os.environ.get("CURELAB_WEB_DIR") or (str(web_default) if web_default.exists() else "")
        return cls(
            pack_dir=pack_dir,
            illness_dir=Path(os.environ.get("CURELAB_ILLNESS_DIR", REPO_ROOT / "illnesses")),
            data_dir=Path(os.environ.get("CURELAB_DATA_DIR", Path.home() / ".curelab")),
            web_dir=Path(web_dir) if web_dir else None,
            kernel=os.environ.get("CURELAB_KERNEL") or None,
            unlock_all=os.environ.get("CURELAB_UNLOCK_ALL", "").lower() in ("1", "true", "yes"),
            balance_path=Path(os.environ["CURELAB_BALANCE"]) if os.environ.get("CURELAB_BALANCE") else None,
        )


@dataclass
class AppState:
    settings: Settings
    pack: Pack
    illnesses: dict[str, Illness]
    balance: Balance
    store: Store
    profile: Profile
    runner: KernelRunner
    grader: Grader
    game: Optional[Game] = None
    last_beat: Optional[float] = None
    last_save: float = 0.0
    read_tokens: dict[str, tuple[str, float]] = field(default_factory=dict)

    # ------------------------------------------------------------------ #

    def campaign(self, campaign_id: str) -> Campaign:
        try:
            return self.pack.campaign(campaign_id)
        except KeyError:
            raise HTTPException(404, f"unknown campaign {campaign_id}")

    def load_game(self) -> None:
        active = self.profile.active
        if active is None:
            self.game = None
            return
        try:
            campaign = self.pack.campaign(active.campaign)
        except KeyError:
            self.profile.active = None
            self.game = None
            return
        self.game = Game(active, campaign, self.illnesses[campaign.illness], self.balance)

    def require_game(self) -> Game:
        if self.game is None:
            raise HTTPException(409, "no game in progress")
        return self.game

    def is_locked(self, campaign: Campaign) -> bool:
        if self.settings.unlock_all or not campaign.unlock_after:
            return False
        return campaign.unlock_after not in self.profile.won

    def save(self, force: bool = True) -> None:
        now = time.monotonic()
        if force or now - self.last_save > 15:
            self.store.save(self.profile)
            self.last_save = now

    def finish_if_over(self) -> None:
        game = self.game
        if game is None or game.state.status == "playing":
            return
        if any(h.get("started_at") == game.state.started_at for h in self.profile.history):
            return
        if game.state.status == "won" and game.campaign.id not in self.profile.won:
            self.profile.won.append(game.campaign.id)
        self.profile.history.append(
            {"campaign": game.campaign.id, "difficulty": game.state.difficulty, "started_at": game.state.started_at, **game.stats()}
        )

    def sync_notes(self, game: Game) -> list[dict[str, Any]]:
        nb = self.profile.notebook(game.campaign.id)
        ev = game.sync_note_rewards(qualifying_notes(nb, self.balance.research_points.note_min_words))
        return [ev.model_dump()] if ev else []


# --------------------------------------------------------------------------- #
# Snapshots
# --------------------------------------------------------------------------- #


def _patient_view(illness: Illness) -> dict[str, Any]:
    p = illness.patient
    return {
        "id": p.id,
        "name": p.name,
        "first_name": p.first_name,
        "age": p.age,
        "sex": p.sex,
        "background": p.background,
        "presenting": p.presenting,
        "companion": p.companion,
        "art": p.art,
        "illness": {"id": illness.id, "name": illness.name, "short": illness.short, "blurb": illness.blurb},
        "fictional_notice": illness.fictional_notice,
    }


def _source_view(pack: Pack, src) -> dict[str, Any]:
    return {
        "vignette": src.vignette,
        "section": src.section,
        "quote": src.quote,
        "site_url": pack.source_pin.site_url(src.vignette),
        "pinned_url": pack.source_pin.blob_url(src.vignette),
        "ref": pack.source_pin.ref,
    }


def game_snapshot(app: AppState, since: int = 0) -> dict[str, Any]:
    game = app.game
    if game is None:
        return {"game": None, "events": [], "cursor": 0}
    s = game.state
    acquired = {t.id: t for t in s.traits if t.id}
    nb = app.profile.notebook(game.campaign.id)
    rp_cfg = app.balance.research_points
    quizzes = []
    for q in game.campaign.quizzes:
        status = game.quiz_status(q.id)
        progress = s.quizzes.get(q.id)
        view: dict[str, Any] = {
            "id": q.id,
            "after": q.after,
            "status": status,
            "points": q.points,
            "wrong_choices": progress.wrong_choices if progress else [],
        }
        if status != "locked":
            view.update({"question": q.question, "choices": q.choices})
        if status == "completed":
            view.update({"answer": q.answer, "explanation": q.explanation, "source": _source_view(app.pack, q.source)})
        quizzes.append(view)
    return {
        "game": {
            "started_at": s.started_at,
            "campaign": game.campaign.id,
            "campaign_title": game.campaign.title,
            "illness": game.illness.id,
            "difficulty": s.difficulty,
            "status": s.status,
            "day": game.day,
            "clock": round(s.clock, 1),
            "health": round(s.health, 2),
            "severity": round(game.severity, 2),
            "decline_per_hour": round(game.decline_per_hour(), 2),
            "stage": s.stage,
            "vitals": game.vitals(),
            "research": s.research,
            "rp": s.rp,
            "errors": s.errors,
            "paused": app.runner.busy,
            "traits": [t.model_dump() for t in s.traits],
            "overlays": sorted({game.illness.trait(t.id).overlay for t in s.traits if t.id and game.illness.trait(t.id).overlay}),
            "tree": [
                {
                    "id": t.id,
                    "name": t.name,
                    "category": t.category,
                    "tier": t.tier,
                    "requires": t.requires,
                    "acquired": t.id in acquired,
                    "day": acquired[t.id].day if t.id in acquired else None,
                    "note": acquired[t.id].note if t.id in acquired else None,
                }
                for t in game.illness.traits
            ],
            "missions": [
                {
                    "id": m.id,
                    "title": m.title,
                    "points": m.points,
                    "status": game.mission_status(m.id),
                    "attempts": s.missions[m.id].attempts if m.id in s.missions else 0,
                    "wrong": s.missions[m.id].wrong if m.id in s.missions else 0,
                    "hints_bought": s.missions[m.id].hints_bought if m.id in s.missions else 0,
                    "hint_total": len(m.hints),
                }
                for m in game.campaign.missions
            ],
            "quizzes": quizzes,
            "pages_read": s.pages_read,
            "notes": {
                "qualifying": qualifying_notes(nb, rp_cfg.note_min_words),
                "awarded": s.note_rp_awarded,
                "cap": game.note_rp_cap(),
            },
            "timeline": [t.model_dump() for t in s.timeline],
            "stats": game.stats(),
        },
        "patient": _patient_view(game.illness),
        "events": [e.model_dump() for e in game.events_since(since)],
        "cursor": s.next_event_id - 1,
    }


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #


class StartBody(BaseModel):
    campaign: str
    difficulty: str = "normal"
    seed: Optional[int] = None


class HeartbeatBody(BaseModel):
    visible: bool = True
    since: int = 0


class CodeBody(BaseModel):
    code: str
    since: int = 0


class AnswerBody(BaseModel):
    choice: int
    since: int = 0


class ReadBody(BaseModel):
    token: str
    since: int = 0


class NoteBody(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    since: int = 0


# --------------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------------- #


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    pack = load_pack(settings.pack_dir)
    illnesses = load_illnesses_for(pack, settings.illness_dir)
    balance = load_balance(settings.balance_path)
    store = Store(settings.data_dir)
    profile = store.load()
    runner = KernelRunner(settings.kernel or pack.kernel, cwd=str(settings.data_dir))
    state = AppState(settings, pack, illnesses, balance, store, profile, runner, Grader(pack, runner))
    state.load_game()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        state.save()
        await runner.shutdown()

    app = FastAPI(title="Cure Lab", lifespan=lifespan)
    app.state.curelab = state

    def rule_error(exc: RuleError) -> HTTPException:
        return HTTPException(409, str(exc))

    # ------------------------------------------------------------ meta
    @app.get("/api/meta")
    async def meta() -> dict[str, Any]:
        campaigns = []
        for c in pack.campaigns:
            ill = illnesses[c.illness]
            campaigns.append(
                {
                    "id": c.id,
                    "title": c.title,
                    "subtitle": c.subtitle,
                    "summary": c.summary,
                    "order": c.order,
                    "datasets": c.datasets,
                    "locked": state.is_locked(c),
                    "unlock_after": c.unlock_after,
                    "won": c.id in profile.won,
                    "total_points": c.total_points,
                    "missions": len(c.missions),
                    "quizzes": len(c.quizzes),
                    "patient": _patient_view(ill),
                }
            )
        return {
            "pack": {
                "id": pack.id,
                "name": pack.name,
                "tool": pack.tool,
                "tool_version": pack.tool_version,
                "language": pack.language,
                "editor_mode": pack.editor_mode,
                "source_pin": pack.source_pin.model_dump(),
            },
            "campaigns": campaigns,
            "difficulties": [
                {"id": k, "label": d.label, "description": d.description} for k, d in balance.difficulties.items()
            ],
            "rules": {
                "hint_cost": balance.research_points.hint_cost,
                "note_min_words": balance.research_points.note_min_words,
                "note_rp": balance.research_points.note_rp,
                "min_read_seconds": balance.research_points.min_read_seconds,
                "seconds_per_day": balance.seconds_per_day,
            },
            "active": state.game.campaign.id if state.game else None,
            "history": profile.history[-20:],
        }

    # ------------------------------------------------------------ game
    @app.post("/api/game/start")
    async def start(body: StartBody) -> dict[str, Any]:
        campaign = state.campaign(body.campaign)
        if state.is_locked(campaign):
            raise HTTPException(403, f"win {campaign.unlock_after} first")
        if body.difficulty not in balance.difficulties:
            raise HTTPException(400, "unknown difficulty")
        state.game = Game.new(campaign, illnesses[campaign.illness], balance, body.difficulty, body.seed)
        profile.active = state.game.state
        state.grader.active_mission = None
        state.read_tokens.clear()
        state.last_beat = None
        state.sync_notes(state.game)
        state.save()
        return game_snapshot(state)

    @app.post("/api/game/abandon")
    async def abandon() -> dict[str, Any]:
        profile.active = None
        state.game = None
        state.grader.active_mission = None
        state.save()
        return game_snapshot(state)

    @app.get("/api/state")
    async def get_state(since: int = 0) -> dict[str, Any]:
        return game_snapshot(state, since)

    @app.post("/api/heartbeat")
    async def heartbeat(body: HeartbeatBody) -> dict[str, Any]:
        game = state.game
        now = time.monotonic()
        gap = 0.0 if state.last_beat is None else now - state.last_beat
        state.last_beat = now
        if game is not None and body.visible and not runner.busy and game.state.status == "playing":
            before = game.state.next_event_id
            game.advance(min(gap, balance.max_heartbeat_gap))
            state.finish_if_over()
            state.save(force=game.state.next_event_id != before)
        return game_snapshot(state, body.since)

    # ------------------------------------------------------------ missions
    def _mission(game: Game, mission_id: str):
        try:
            return game.campaign.mission(mission_id)
        except KeyError:
            raise HTTPException(404, f"unknown mission {mission_id}")

    @app.get("/api/missions/{mission_id}")
    async def mission_detail(mission_id: str) -> dict[str, Any]:
        game = state.require_game()
        m = _mission(game, mission_id)
        progress = game.state.missions.get(mission_id)
        bought = progress.hints_bought if progress else 0
        return {
            "id": m.id,
            "title": m.title,
            "points": m.points,
            "status": game.mission_status(m.id),
            "briefing": game.illness.fill(m.briefing),
            "task": m.task,
            "starter_code": m.starter_code,
            "source": _source_view(pack, m.source),
            "hints": m.hints[:bought],
            "hint_total": len(m.hints),
            "hint_cost": balance.research_points.hint_cost,
            "notebook_pages": [{"id": p, "title": game.campaign.page(p).title} for p in m.notebook_pages],
            "attempts": progress.attempts if progress else 0,
            "timeout": m.timeout,
        }

    @app.post("/api/missions/{mission_id}/start")
    async def mission_start(mission_id: str) -> dict[str, Any]:
        game = state.require_game()
        m = _mission(game, mission_id)
        try:
            game.check_mission_open(mission_id)
        except RuleError as exc:
            raise rule_error(exc)
        res = await state.grader.prepare(m)
        if not res.ok:
            return JSONResponse(
                status_code=500,
                content={"detail": "Mission setup failed. This is a bug in the pack, not your code.", "execution": res.to_dict()},
            )
        return {"ok": True, "execution": res.to_dict()}

    @app.post("/api/missions/{mission_id}/run")
    async def mission_run(mission_id: str, body: CodeBody) -> dict[str, Any]:
        game = state.require_game()
        m = _mission(game, mission_id)
        try:
            game.check_mission_open(mission_id)
        except RuleError as exc:
            raise rule_error(exc)
        setup = await state.grader.ensure(m)
        if setup is not None and not setup.ok:
            raise HTTPException(500, "Mission setup failed. This is a bug in the pack, not your code.")
        res = await state.grader.run(m, body.code)
        help_ = debug_help(pack, m, res.error_text()) if res.status == "error" else []
        return {"execution": res.to_dict(), "debug": help_, **game_snapshot(state, body.since)}

    @app.post("/api/missions/{mission_id}/submit")
    async def mission_submit(mission_id: str, body: CodeBody) -> dict[str, Any]:
        game = state.require_game()
        m = _mission(game, mission_id)
        if not body.code.strip():
            raise HTTPException(400, "write some code before submitting")
        try:
            game.check_mission_open(mission_id)
        except RuleError as exc:
            raise rule_error(exc)
        if game.mission_status(mission_id) == "completed":
            raise HTTPException(409, "mission already completed")
        setup = await state.grader.ensure(m)
        if setup is not None and not setup.ok:
            raise HTTPException(500, "Mission setup failed. This is a bug in the pack, not your code.")
        outcome = await state.grader.submit(m, body.code)
        if outcome.graded and game.state.status == "playing":
            game.record_submission(mission_id, outcome.passed, cause=f"mission {m.title}")
            state.sync_notes(game)
            state.finish_if_over()
        state.save()
        return {"outcome": outcome.to_dict(), **game_snapshot(state, body.since)}

    @app.post("/api/missions/{mission_id}/hint")
    async def mission_hint(mission_id: str, since: int = Query(0)) -> dict[str, Any]:
        game = state.require_game()
        m = _mission(game, mission_id)
        try:
            tier = game.buy_hint(mission_id)
        except RuleError as exc:
            raise rule_error(exc)
        state.save()
        return {"tier": tier, "text": m.hints[tier], **game_snapshot(state, since)}

    @app.post("/api/missions/{mission_id}/debug")
    async def mission_debug(mission_id: str) -> dict[str, Any]:
        game = state.require_game()
        m = _mission(game, mission_id)
        text = state.grader.last_error if state.grader.active_mission == mission_id else ""
        return {"error": text, "help": debug_help(pack, m, text)}

    # ------------------------------------------------------------ quizzes
    @app.post("/api/quizzes/{quiz_id}/answer")
    async def quiz_answer(quiz_id: str, body: AnswerBody) -> dict[str, Any]:
        game = state.require_game()
        try:
            game.campaign.quiz(quiz_id)
        except KeyError:
            raise HTTPException(404, f"unknown quiz {quiz_id}")
        try:
            correct, _ = game.answer_quiz(quiz_id, body.choice)
        except RuleError as exc:
            raise rule_error(exc)
        state.finish_if_over()
        state.save()
        return {"correct": correct, **game_snapshot(state, body.since)}

    # ------------------------------------------------------------ notebook
    def _notebook_campaign(campaign_id: Optional[str]) -> Campaign:
        if campaign_id:
            return state.campaign(campaign_id)
        if state.game is None:
            raise HTTPException(409, "no game in progress; pass ?campaign=")
        return state.game.campaign

    def _note_view(note: Note) -> dict[str, Any]:
        words = word_count(note.body)
        return {**note.model_dump(), "words": words, "qualifies": words >= balance.research_points.note_min_words}

    @app.get("/api/notebook")
    async def notebook(campaign: Optional[str] = None) -> dict[str, Any]:
        c = _notebook_campaign(campaign)
        nb = profile.notebook(c.id)
        read = set(state.game.state.pages_read) if state.game and state.game.campaign.id == c.id else set()
        pages = []
        for p in c.notebook:
            pages.append(
                {
                    "id": p.id,
                    "title": p.title,
                    "rp": p.rp,
                    "missions": p.missions,
                    "read": p.id in read,
                    "blocks": [
                        {
                            "kind": b.kind,
                            "text": b.text,
                            "source": _source_view(pack, b.source) if b.source else None,
                        }
                        for b in p.blocks
                    ],
                }
            )
        return {"campaign": c.id, "pages": pages, "notes": [_note_view(n) for n in nb.notes]}

    @app.post("/api/notebook/pages/{page_id}/open")
    async def page_open(page_id: str) -> dict[str, Any]:
        game = state.require_game()
        try:
            game.campaign.page(page_id)
        except KeyError:
            raise HTTPException(404, "unknown page")
        token = secrets.token_hex(8)
        state.read_tokens[page_id] = (token, time.monotonic())
        return {"token": token, "min_read_seconds": balance.research_points.min_read_seconds}

    @app.post("/api/notebook/pages/{page_id}/read")
    async def page_read(page_id: str, body: ReadBody) -> dict[str, Any]:
        game = state.require_game()
        try:
            game.campaign.page(page_id)
        except KeyError:
            raise HTTPException(404, "unknown page")
        issued = state.read_tokens.get(page_id)
        if not issued or issued[0] != body.token:
            raise HTTPException(409, "open the page before marking it read")
        if time.monotonic() - issued[1] < balance.research_points.min_read_seconds:
            raise HTTPException(409, "give the page a proper read first")
        game.read_page(page_id)
        state.save()
        return game_snapshot(state, body.since)

    @app.post("/api/notebook/notes")
    async def note_create(body: NoteBody, campaign: Optional[str] = None) -> dict[str, Any]:
        c = _notebook_campaign(campaign)
        nb = profile.notebook(c.id)
        note = Note(title=(body.title or "").strip() or f"My notes, page {len(nb.notes) + 1}", body=body.body or "")
        nb.notes.append(note)
        if state.game and state.game.campaign.id == c.id:
            state.sync_notes(state.game)
        state.save()
        return {"note": _note_view(note), **game_snapshot(state, body.since)}

    @app.put("/api/notebook/notes/{note_id}")
    async def note_update(note_id: str, body: NoteBody, campaign: Optional[str] = None) -> dict[str, Any]:
        c = _notebook_campaign(campaign)
        nb = profile.notebook(c.id)
        try:
            note = nb.get(note_id)
        except KeyError:
            raise HTTPException(404, "unknown note")
        if body.title is not None:
            note.title = body.title.strip() or note.title
        if body.body is not None:
            note.body = body.body
        note.updated = _now()
        if state.game and state.game.campaign.id == c.id:
            state.sync_notes(state.game)
        state.save()
        return {"note": _note_view(note), **game_snapshot(state, body.since)}

    @app.delete("/api/notebook/notes/{note_id}")
    async def note_delete(note_id: str, campaign: Optional[str] = None) -> dict[str, Any]:
        c = _notebook_campaign(campaign)
        nb = profile.notebook(c.id)
        nb.notes = [n for n in nb.notes if n.id != note_id]
        state.save()
        return {"ok": True}

    @app.get("/api/notebook/export")
    async def notebook_export(scope: str = "all", campaign: Optional[str] = None) -> PlainTextResponse:
        if scope not in ("all", "mine"):
            raise HTTPException(400, "scope must be 'all' or 'mine'")
        c = _notebook_campaign(campaign)
        game = state.game if state.game and state.game.campaign.id == c.id else None
        text = export_markdown(pack, c, illnesses[c.illness], profile.notebook(c.id), scope, game)  # type: ignore[arg-type]
        filename = f"curelab-{c.id}-{'notebook' if scope == 'all' else 'my-notes'}.md"
        return PlainTextResponse(
            text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "kernel": runner.kernel_name, "kernel_started": runner.started}

    # ------------------------------------------------------------ static web
    if settings.web_dir and Path(settings.web_dir).exists():
        app.mount("/", StaticFiles(directory=str(settings.web_dir), html=True), name="web")

    return app


def app_factory() -> FastAPI:  # for `uvicorn curelab.app:app_factory --factory`
    return create_app()
