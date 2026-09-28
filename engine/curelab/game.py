"""Game state and rules.

The state is a plain pydantic model so it can be saved as JSON; ``Game`` wraps
it with the campaign, illness and balance needed to apply the rules.
"""

from __future__ import annotations

import datetime as _dt
import random
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from . import patient as patient_mod
from .balance import Balance
from .content import Campaign, Illness
from .evolution import evolve

Status = Literal["playing", "won", "lost"]


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


class AcquiredTrait(BaseModel):
    id: Optional[str]  # None for a "further progression" bump
    name: str
    day: int
    gain: float
    note: str
    cause: str


class MissionProgress(BaseModel):
    attempts: int = 0
    wrong: int = 0
    completed: bool = False
    completed_day: Optional[int] = None
    hints_bought: int = 0
    # the learner's code that passed the check (for the script export)
    passed_code: Optional[str] = None


class QuizProgress(BaseModel):
    wrong_choices: list[int] = []
    correct: bool = False


class TimelineEntry(BaseModel):
    day: int
    kind: str  # admit | trait | stage | mission | quiz | rp | end
    text: str


class Event(BaseModel):
    id: int
    kind: str
    title: str
    text: str = ""
    data: dict[str, Any] = {}


class ConsultMessage(BaseModel):
    """One turn of a "consult another doctor" conversation."""

    role: Literal["user", "assistant"]
    text: str  # what the learner typed / the doctor's answer
    # for a question: exactly what was sent (game context + question), so the
    # history is resent byte for byte and stays cacheable
    prompt: str = ""
    mission_id: Optional[str] = None
    day: int = 1

    def public(self) -> dict[str, Any]:
        return {"role": self.role, "text": self.text, "mission_id": self.mission_id, "day": self.day}


class GameState(BaseModel):
    campaign: str
    illness: str
    difficulty: str
    seed: int
    status: Status = "playing"
    clock: float = 0.0  # seconds of active play
    health: float = 100.0
    trait_severity: float = 0.0
    traits: list[AcquiredTrait] = []
    research: int = 0
    missions: dict[str, MissionProgress] = {}
    quizzes: dict[str, QuizProgress] = {}
    rp: int = 0
    rp_earned: int = 0
    rp_spent: int = 0
    pages_read: list[str] = []
    note_rp_awarded: int = 0
    errors: int = 0
    timeline: list[TimelineEntry] = []
    events: list[Event] = []
    next_event_id: int = 1
    consult: list[ConsultMessage] = []
    stage: str = "stable"
    started_at: str = Field(default_factory=_now)
    ended_at: Optional[str] = None


class RuleError(Exception):
    """An action that the rules do not allow (e.g. a locked mission)."""


class Game:
    def __init__(self, state: GameState, campaign: Campaign, illness: Illness, balance: Balance):
        self.state = state
        self.campaign = campaign
        self.illness = illness
        self.balance = balance

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def new(
        cls,
        campaign: Campaign,
        illness: Illness,
        balance: Balance,
        difficulty: str = "normal",
        seed: Optional[int] = None,
    ) -> "Game":
        balance.difficulty(difficulty)  # validate
        state = GameState(
            campaign=campaign.id,
            illness=illness.id,
            difficulty=difficulty,
            seed=seed if seed is not None else random.SystemRandom().randrange(1, 2**31),
            rp=balance.research_points.start,
        )
        game = cls(state, campaign, illness, balance)
        game._note("admit", illness.fill(illness.admit_note))
        return game

    # ------------------------------------------------------------------ #
    # Derived values
    # ------------------------------------------------------------------ #

    @property
    def day(self) -> int:
        return 1 + int(self.state.clock // self.balance.seconds_per_day)

    def severity_at(self, clock: float) -> float:
        b = self.balance
        creep = b.creep_per_hour * b.difficulty(self.state.difficulty).creep_mult
        return max(0.0, min(100.0, b.s0 + creep * clock / 3600.0 + self.state.trait_severity))

    @property
    def severity(self) -> float:
        return self.severity_at(self.state.clock)

    def decline_per_hour(self, severity: Optional[float] = None) -> float:
        s = self.severity if severity is None else severity
        return self.balance.h_max_per_hour * (s / 100.0) ** self.balance.exponent

    @property
    def acquired_ids(self) -> list[str]:
        return [t.id for t in self.state.traits if t.id]

    def vitals(self) -> dict[str, float]:
        return patient_mod.vitals(self.illness, self.state.health, self.acquired_ids, self.state.status)

    def mission_status(self, mission_id: str) -> str:
        progress = self.state.missions.get(mission_id)
        if progress and progress.completed:
            return "completed"
        idx = self.campaign.mission_index(mission_id)
        if idx == 0:
            return "available"
        prev = self.campaign.missions[idx - 1].id
        prev_progress = self.state.missions.get(prev)
        return "available" if prev_progress and prev_progress.completed else "locked"

    def quiz_status(self, quiz_id: str) -> str:
        quiz = self.campaign.quiz(quiz_id)
        progress = self.state.quizzes.get(quiz_id)
        if progress and progress.correct:
            return "completed"
        after = self.state.missions.get(quiz.after)
        return "available" if after and after.completed else "locked"

    def missions_attempted(self) -> int:
        return sum(1 for p in self.state.missions.values() if p.attempts > 0)

    # ------------------------------------------------------------------ #
    # Time
    # ------------------------------------------------------------------ #

    def advance(self, seconds: float, step: float = 5.0) -> None:
        """Advance active play time; the patient declines as severity builds."""
        if self.state.status != "playing" or seconds <= 0:
            return
        remaining = seconds
        while remaining > 0 and self.state.status == "playing":
            dt = min(step, remaining)
            # midpoint severity for this step
            s_mid = self.severity_at(self.state.clock + dt / 2)
            self.state.health -= self.decline_per_hour(s_mid) * dt / 3600.0
            self.state.clock += dt
            remaining -= dt
            if self.state.health <= 0:
                self.state.health = 0.0
                self._lose()
            else:
                self._update_stage()

    def _update_stage(self) -> None:
        stage = self.balance.stage_for(self.state.health)
        if stage != self.state.stage:
            previous = self.state.stage
            self.state.stage = stage
            template = self.illness.stage_notes.get(stage)
            text = self.illness.fill(template) if template else f"Condition changed: {stage}."
            self._note("stage", text)
            self._event("stage", f"Condition: {stage}", text, {"from": previous, "to": stage})

    # ------------------------------------------------------------------ #
    # Wrong attempts and evolution
    # ------------------------------------------------------------------ #

    def wrong_attempt(self, cause: str) -> Optional[Event]:
        """Register an error; the disease evolves one trait."""
        if self.state.status != "playing":
            return None
        self.state.errors += 1
        rng = random.Random(self.state.seed * 1_000_003 + self.state.errors)
        evo = evolve(self.illness, self.acquired_ids, self.balance, self.state.difficulty, rng)
        self.state.trait_severity += evo.gain
        if evo.trait is None:
            name = "Further progression"
            note = self.illness.fill(self.illness.progression_note)
            data = {"trait": None, "category": "progression", "overlay": None}
        else:
            name = evo.trait.name
            note = self.illness.fill(evo.trait.note)
            data = {
                "trait": evo.trait.id,
                "category": evo.trait.category,
                "overlay": evo.trait.overlay,
                "tier": evo.trait.tier,
                "event": evo.trait.is_event,
                "neutral": evo.trait.neutral,
            }
        data.update({"gain": round(evo.gain, 2), "severity": round(self.severity, 1), "cause": cause})
        self.state.traits.append(
            AcquiredTrait(id=data["trait"], name=name, day=self.day, gain=round(evo.gain, 3), note=note, cause=cause)
        )
        self._note("event" if data.get("event") else "trait", note)
        return self._event("trait", name, note, data)

    # ------------------------------------------------------------------ #
    # Missions and quizzes
    # ------------------------------------------------------------------ #

    def _require_playing(self) -> None:
        if self.state.status != "playing":
            raise RuleError("this game is over")

    def _mission_progress(self, mission_id: str) -> MissionProgress:
        self.campaign.mission(mission_id)  # raises KeyError if unknown
        return self.state.missions.setdefault(mission_id, MissionProgress())

    def check_mission_open(self, mission_id: str) -> None:
        self._require_playing()
        status = self.mission_status(mission_id)
        if status == "locked":
            raise RuleError("complete the previous mission first")

    def record_submission(self, mission_id: str, passed: bool, cause: str = "", code: Optional[str] = None) -> list[Event]:
        """Apply the outcome of a graded submission (``code`` is kept if it passed)."""
        self.check_mission_open(mission_id)
        progress = self._mission_progress(mission_id)
        if progress.completed:
            return []
        progress.attempts += 1
        events: list[Event] = []
        if passed:
            mission = self.campaign.mission(mission_id)
            progress.completed = True
            progress.completed_day = self.day
            progress.passed_code = code
            self.state.research = min(100, self.state.research + mission.points)
            text = f"Lab: “{mission.title}” complete. Cure research +{mission.points}%."
            self._note("mission", text)
            events.append(self._event("mission", mission.title, text, {"mission": mission_id, "points": mission.points}))
            events.extend(self._check_win())
        else:
            progress.wrong += 1
            ev = self.wrong_attempt(cause or f"mission {mission_id}")
            if ev:
                events.append(ev)
        return events

    def answer_quiz(self, quiz_id: str, choice: int) -> tuple[bool, list[Event]]:
        self._require_playing()
        quiz = self.campaign.quiz(quiz_id)
        if self.quiz_status(quiz_id) == "locked":
            raise RuleError("finish the related mission first")
        progress = self.state.quizzes.setdefault(quiz_id, QuizProgress())
        if progress.correct:
            return True, []
        if not 0 <= choice < len(quiz.choices):
            raise RuleError("invalid choice")
        if choice in progress.wrong_choices:
            raise RuleError("you already ruled that answer out")
        if choice == quiz.answer:
            progress.correct = True
            self.state.research = min(100, self.state.research + quiz.points)
            text = f"Journal club: answered correctly. Cure research +{quiz.points}%."
            self._note("quiz", text)
            events = [self._event("quiz", "Correct!", text, {"quiz": quiz_id, "points": quiz.points})]
            events.extend(self._check_win())
            return True, events
        progress.wrong_choices.append(choice)
        ev = self.wrong_attempt(f"quiz {quiz_id}")
        return False, [ev] if ev else []

    def _check_win(self) -> list[Event]:
        if self.state.status == "playing" and self.state.research >= 100 and self.state.health > 0:
            self.state.status = "won"
            self.state.stage = "cured"
            self.state.ended_at = _now()
            text = self.illness.fill(self.illness.cure_note)
            self._note("end", text)
            return [self._event("won", "Cure found!", text, {})]
        return []

    def _lose(self) -> None:
        if self.state.status != "playing":
            return
        self.state.status = "lost"
        self.state.stage = "deceased"
        self.state.ended_at = _now()
        text = self.illness.fill(self.illness.loss_note)
        self._note("end", text)
        self._event("lost", f"In memory of {self.illness.patient.name}", text, {})

    # ------------------------------------------------------------------ #
    # Research points
    # ------------------------------------------------------------------ #

    def _award_rp(self, amount: int, reason: str) -> Optional[Event]:
        if amount <= 0:
            return None
        self.state.rp += amount
        self.state.rp_earned += amount
        return self._event("rp", f"+{amount} RP", reason, {"amount": amount})

    def buy_hint(self, mission_id: str) -> int:
        """Spend RP on the next hint tier; returns the tier index now unlocked."""
        self.check_mission_open(mission_id)
        mission = self.campaign.mission(mission_id)
        progress = self._mission_progress(mission_id)
        if progress.hints_bought >= len(mission.hints):
            raise RuleError("no more hints for this mission")
        cost = self.balance.research_points.hint_cost
        if self.state.rp < cost:
            raise RuleError(f"not enough research points (need {cost})")
        self.state.rp -= cost
        self.state.rp_spent += cost
        progress.hints_bought += 1
        return progress.hints_bought - 1

    def read_page(self, page_id: str) -> Optional[Event]:
        page = self.campaign.page(page_id)
        if page_id in self.state.pages_read:
            return None
        self.state.pages_read.append(page_id)
        if self.state.status != "playing":
            return None
        return self._award_rp(page.rp, f"Read “{page.title}”.")

    def note_rp_cap(self) -> int:
        cap_rule = self.balance.research_points.note_cap
        if cap_rule == "missions_attempted":
            return self.missions_attempted()
        if cap_rule == "none":
            return 10**6
        return int(cap_rule)

    def sync_note_rewards(self, qualifying_notes: int) -> Optional[Event]:
        """Award RP for the learner's own note pages, up to the cap."""
        if self.state.status != "playing":
            return None
        rp = self.balance.research_points
        allowed = min(qualifying_notes, self.note_rp_cap())
        new = allowed - self.state.note_rp_awarded
        if new <= 0:
            return None
        self.state.note_rp_awarded += new
        return self._award_rp(new * rp.note_rp, "Your own lab notes.")

    # ------------------------------------------------------------------ #
    # Bookkeeping
    # ------------------------------------------------------------------ #

    def _note(self, kind: str, text: str) -> None:
        self.state.timeline.append(TimelineEntry(day=self.day, kind=kind, text=text))

    def _event(self, kind: str, title: str, text: str = "", data: Optional[dict[str, Any]] = None) -> Event:
        ev = Event(id=self.state.next_event_id, kind=kind, title=title, text=text, data=data or {})
        self.state.next_event_id += 1
        self.state.events.append(ev)
        # keep the event log bounded; the timeline is the durable record
        if len(self.state.events) > 200:
            self.state.events = self.state.events[-200:]
        return ev

    def events_since(self, cursor: int) -> list[Event]:
        return [e for e in self.state.events if e.id > cursor]

    def stats(self) -> dict[str, Any]:
        s = self.state
        return {
            "status": s.status,
            "days": self.day,
            "active_minutes": round(s.clock / 60, 1),
            "errors": s.errors,
            "traits": sum(1 for t in s.traits if not (t.id and self.illness.trait(t.id).is_event)),
            "events": sum(1 for t in s.traits if t.id and self.illness.trait(t.id).is_event),
            "missions_completed": sum(1 for p in s.missions.values() if p.completed),
            "missions_total": len(self.campaign.missions),
            "quizzes_correct": sum(1 for p in s.quizzes.values() if p.correct),
            "quizzes_total": len(self.campaign.quizzes),
            "hints_bought": sum(p.hints_bought for p in s.missions.values()),
            "rp_earned": s.rp_earned,
            "rp_spent": s.rp_spent,
            "pages_read": len(s.pages_read),
            "research": s.research,
            "final_health": round(s.health, 1),
        }
