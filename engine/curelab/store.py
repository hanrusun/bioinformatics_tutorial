"""JSON persistence for the single local player profile."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from .game import GameState
from .notebook import Notebook

PROFILE_VERSION = 1


class Profile(BaseModel):
    version: int = PROFILE_VERSION
    won: list[str] = []
    active: Optional[GameState] = None
    notebooks: dict[str, Notebook] = {}
    history: list[dict[str, Any]] = []
    # chat model and effort chosen in the game, per chat ("consult" / "bedside");
    # empty values keep the defaults from .env
    chat: dict[str, dict[str, str]] = {}

    def notebook(self, campaign_id: str) -> Notebook:
        return self.notebooks.setdefault(campaign_id, Notebook())


class Store:
    def __init__(self, data_dir: Path | str):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "profile.json"

    def load(self) -> Profile:
        if not self.path.exists():
            return Profile()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Profile.model_validate(data)
        except (ValueError, json.JSONDecodeError):
            # keep a copy of the unreadable file rather than silently discarding it
            backup = self.path.with_suffix(".corrupt.json")
            self.path.replace(backup)
            return Profile()

    def save(self, profile: Profile) -> None:
        payload = profile.model_dump_json(indent=1)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".profile-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
