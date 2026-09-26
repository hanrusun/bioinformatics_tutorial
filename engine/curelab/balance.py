"""Balance configuration (difficulty, decline curve, research-point economy)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_BALANCE = Path(__file__).with_name("balance.yaml")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Difficulty(_Model):
    label: str
    description: str
    creep_mult: float
    gain_mult: float


class Stage(_Model):
    name: str
    min_health: float


class RPConfig(_Model):
    start: int = 0
    hint_cost: int = 1
    note_min_words: int = 40
    note_rp: int = 1
    note_cap: str = "missions_attempted"
    min_read_seconds: float = 4


class Targets(_Model):
    idle_survival_hours_min: float
    careful_final_health_min: float
    typical_win_rate_min: float
    typical_median_health: tuple[float, float]
    reckless_loss_rate_min: float


class Balance(_Model):
    s0: float
    creep_per_hour: float
    h_max_per_hour: float
    exponent: float
    gain_scale: float
    exhausted_gain: tuple[float, float]
    tier_weight_exponent: float
    seconds_per_day: float
    max_heartbeat_gap: float
    stages: list[Stage]
    difficulties: dict[str, Difficulty]
    research_points: RPConfig
    targets: Optional[Targets] = None

    def difficulty(self, key: str) -> Difficulty:
        try:
            return self.difficulties[key]
        except KeyError as exc:
            raise KeyError(f"unknown difficulty '{key}'") from exc

    def stage_for(self, health: float) -> str:
        if health <= 0:
            return "deceased"
        for stage in self.stages:
            if health >= stage.min_health:
                return stage.name
        return self.stages[-1].name


def load_balance(path: Path | str | None = None) -> Balance:
    with Path(path or DEFAULT_BALANCE).open("r", encoding="utf-8") as fh:
        return Balance.model_validate(yaml.safe_load(fh))
