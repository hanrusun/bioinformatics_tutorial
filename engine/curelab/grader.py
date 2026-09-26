"""Mission lifecycle in the kernel: setup, free runs, graded submissions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .content import DebugRule, Mission, Pack
from .runner import ExecResult, KernelRunner

RESULT_SENTINEL = "@@CURELAB_RESULT@@"


@dataclass
class CheckResult:
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubmitOutcome:
    graded: bool  # False for timeouts / infrastructure problems (never penalized)
    passed: bool
    message: str
    execution: ExecResult
    check: Optional[CheckResult] = None
    debug: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graded": self.graded,
            "passed": self.passed,
            "message": self.message,
            "execution": self.execution.to_dict(),
            "debug": self.debug,
        }


def parse_check_output(res: ExecResult) -> CheckResult:
    for line in res.stdout.splitlines():
        idx = line.find(RESULT_SENTINEL)
        if idx >= 0:
            try:
                payload = json.loads(line[idx + len(RESULT_SENTINEL) :].strip())
            except json.JSONDecodeError:
                break
            passed = payload.get("pass")
            if isinstance(passed, list):  # R's jsonlite may box scalars
                passed = bool(passed[0]) if passed else False
            message = payload.get("message", "")
            if isinstance(message, list):
                message = " ".join(str(m) for m in message)
            return CheckResult(bool(passed), str(message), payload.get("details") or {})
    detail = res.error_text() or res.stderr.strip()
    return CheckResult(False, "The checker could not evaluate your work" + (f": {detail}" if detail else "."))


def debug_help(pack: Pack, mission: Optional[Mission], error_text: str) -> list[str]:
    """Explain an error message using mission-level, then pack-level, rules."""
    if not error_text:
        return []
    rules: list[DebugRule] = (list(mission.debug) if mission else []) + list(pack.debug)
    found: list[str] = []
    for rule in rules:
        try:
            if re.search(rule.pattern, error_text, flags=re.IGNORECASE | re.MULTILINE) and rule.help not in found:
                found.append(rule.help)
        except re.error:
            continue
    return found


class Grader:
    def __init__(self, pack: Pack, runner: KernelRunner):
        self.pack = pack
        self.runner = runner
        self.active_mission: Optional[str] = None
        self.last_error: str = ""

    async def prepare(self, mission: Mission) -> ExecResult:
        """Fresh kernel + pack init + mission setup (loads the mission checkpoint)."""
        await self.runner.restart()
        code = "\n".join(
            part
            for part in (self.pack.render_init(), self.pack.render_prelude(mission.id), mission.setup)
            if part and part.strip()
        )
        res = await self.runner.execute(code, timeout=max(mission.timeout, 600)) if code else ExecResult()
        self.active_mission = mission.id if res.ok else None
        self.last_error = ""
        return res

    async def ensure(self, mission: Mission) -> Optional[ExecResult]:
        if self.active_mission == mission.id and self.runner.started:
            return None
        return await self.prepare(mission)

    async def run(self, mission: Mission, code: str) -> ExecResult:
        res = await self.runner.execute(code, timeout=mission.timeout)
        if res.status == "error":
            self.last_error = res.error_text()
        return res

    async def submit(self, mission: Mission, code: str) -> SubmitOutcome:
        res = await self.runner.execute(code, timeout=mission.timeout)
        if res.status == "timeout":
            self.active_mission = None if not self.runner.started else self.active_mission
            return SubmitOutcome(False, False, res.error["evalue"] if res.error else "Timed out.", res)
        if res.status == "error":
            self.last_error = res.error_text()
            if res.error and res.error.get("ename") == "KernelDied":
                self.active_mission = None
                return SubmitOutcome(False, False, "The kernel crashed (often out of memory). The bench was reset; try again.", res)
            return SubmitOutcome(
                True,
                False,
                "Your code stopped with an error.",
                res,
                debug=debug_help(self.pack, mission, self.last_error),
            )
        check_code = "\n".join(p for p in (self.pack.render_prelude(mission.id), mission.check) if p.strip())
        check_res = await self.runner.execute(check_code, timeout=max(120, mission.timeout))
        check = parse_check_output(check_res)
        if check_res.status == "timeout":
            return SubmitOutcome(False, False, "The checker timed out; the attempt was not counted.", res, check)
        if not check.passed:
            self.last_error = check.message
        return SubmitOutcome(
            True,
            check.passed,
            check.message,
            res,
            check,
            debug=[] if check.passed else debug_help(self.pack, mission, check.message),
        )
