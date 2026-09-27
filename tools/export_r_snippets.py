#!/usr/bin/env python3
"""Print every piece of R code in a pack as JSON (for tools/rcheck).

Includes the pack's R files, mission setup/solution/check/expected/wrong
code, the code in each mission's last hint, and notebook code blocks.
Starter code is excluded on purpose: it has blanks for the learner to fill.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from curelab.content import load_pack  # noqa: E402


def main(*pack_dirs: str) -> None:
    dirs = pack_dirs or [str(p.parent) for p in sorted((ROOT / "packs").glob("*/pack.yaml"))]
    snippets = []
    for pack_dir in dirs:
        snippets += pack_snippets(pack_dir)
    json.dump(snippets, sys.stdout, indent=1)


def pack_snippets(pack_dir: str) -> list[dict]:
    pack = load_pack(pack_dir)
    snippets = []
    for path in sorted(Path(pack_dir).rglob("*.R")):
        snippets.append({"where": str(path.relative_to(ROOT)), "code": path.read_text()})
    snippets.append({"where": "pack init_code", "code": pack.render_init()})
    for c in pack.campaigns:
        for m in c.missions:
            for field in ("setup", "solution", "check", "build_report"):
                snippets.append({"where": f"{m.id}.{field}", "code": getattr(m, field)})
            for key, expr in m.expected.items():
                snippets.append({"where": f"{m.id}.expected.{key}", "code": expr})
            for i, w in enumerate(m.wrong_solutions):
                snippets.append({"where": f"{m.id}.wrong_solutions[{i}]", "code": w.code})
            if "```r" in m.hints[-1]:
                code = m.hints[-1].split("```r", 1)[1].split("```", 1)[0]
                snippets.append({"where": f"{m.id}.hints[-1]", "code": code})
        for p in c.notebook:
            for i, b in enumerate(p.blocks):
                if b.kind == "code":
                    snippets.append({"where": f"{p.id}.blocks[{i}]", "code": b.text})
    for s in snippets:
        s["where"] = f"{pack.id}: {s['where']}"
    return snippets


if __name__ == "__main__":
    main(*sys.argv[1:])  # no arguments: every pack under packs/
