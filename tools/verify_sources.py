#!/usr/bin/env python3
"""Verify that tutorial content is grounded in the pinned upstream sources.

For a pack (default ``packs/seurat``) this checks, against the source
documents at the exact revision in ``pack.yaml`` (``source_pin``):

* every cited document exists and every cited ``section`` is a heading in it;
* every ``quote`` (missions, quizzes, notebook pages) appears verbatim;
* every notebook ``code`` block appears verbatim;
* every line of a mission ``solution`` appears verbatim, except lines ending
  in ``# curelab: adapted`` (e.g. a local data path), which are reported.
  A line may store a verbatim call in a new variable: for
  ``b_cells <- subset(x = pbmc, idents = 'B')`` it is enough that
  ``subset(x = pbmc, idents = 'B')`` appears in the source.

Comparison ignores whitespace runs and Markdown emphasis/link syntax, nothing
else. It also writes ``docs/SOURCES.md``: an index of every item and its
source.

Usage:
    python tools/verify_sources.py [--pack packs/seurat] [--source-dir DIR] [--no-write]
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from curelab.content import Pack, Source, load_pack  # noqa: E402

ADAPTED = "# curelab: adapted"
ASSIGNMENT = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.]*\s*(<-|=)\s*(?=\S)")
CACHE = ROOT / ".cache" / "sources"


def normalize(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [label](url) -> label
    text = text.replace("`", "").replace("*", "")
    text = text.replace("\\", "")  # Rmd escapes such as \  and \_
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def heading_texts(document: str) -> set[str]:
    heads = set()
    for line in document.splitlines():
        m = re.match(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            heads.add(normalize(m.group(1)).lower())
        for s in re.findall(r"<summary>(.*?)</summary>", line):
            heads.add(normalize(s).lower())
    return heads


def fetch(pack: Pack, citation: str, source_dir: Path | None) -> str:
    pin, document = pack.resolve_source(citation)
    if source_dir is not None:
        # a pack citing several repositories keeps each one's documents in a subfolder
        key = citation.partition(":")[0] if pin is not pack.source_pin else ""
        return (source_dir / key / document).read_text(encoding="utf-8")
    cached = CACHE / pin.repo.replace("/", "__") / pin.ref / document
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    with urllib.request.urlopen(pin.raw_url(document), timeout=60) as resp:  # noqa: S310 (fixed https host)
        text = resp.read().decode("utf-8")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    adapted: list[str] = field(default_factory=list)
    checked: int = 0


def verify(pack: Pack, source_dir: Path | None) -> Report:
    rep = Report()
    docs: dict[str, str] = {}

    def doc(name: str) -> str | None:
        if name not in docs:
            try:
                docs[name] = fetch(pack, name, source_dir)
            except Exception as exc:  # noqa: BLE001
                rep.errors.append(f"cannot fetch {name}: {exc}")
                docs[name] = ""
        return docs[name] or None

    def check_source(where: str, src: Source, require_quote: bool = False) -> None:
        text = doc(src.vignette)
        if text is None:
            return
        rep.checked += 1
        if normalize(src.section).lower() not in heading_texts(text):
            rep.errors.append(f"{where}: section “{src.section}” is not a heading in {src.vignette}")
        if src.quote:
            rep.checked += 1
            if normalize(src.quote) not in normalize(text):
                rep.errors.append(f"{where}: quote not found verbatim in {src.vignette}: “{src.quote[:90]}…”")
        elif require_quote:
            rep.errors.append(f"{where}: needs a verbatim quote")

    def check_snippet(where: str, snippet: str, src: Source, allow_adapted: bool) -> None:
        text = doc(src.vignette)
        if text is None:
            return
        body = normalize(text)
        for raw in snippet.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.endswith(ADAPTED):
                if allow_adapted:
                    rep.adapted.append(f"{where}: {line[: -len(ADAPTED)].strip()}")
                    continue
                rep.errors.append(f"{where}: adapted lines are not allowed here")
            rep.checked += 1
            if normalize(line) in body:
                continue
            call = ASSIGNMENT.sub("", line)
            if call != line and normalize(call) in body:
                continue
            rep.errors.append(f"{where}: code line not found in {src.vignette}: {line}")

    for campaign in pack.campaigns:
        for m in campaign.missions:
            check_source(f"{campaign.id}/{m.id}", m.source)
            if m.verbatim_solution:
                check_snippet(f"{campaign.id}/{m.id} solution", m.solution, m.source, allow_adapted=True)
        for q in campaign.quizzes:
            check_source(f"{campaign.id}/{q.id}", q.source, require_quote=True)
        for p in campaign.notebook:
            for i, b in enumerate(p.blocks):
                if b.source is None:
                    continue
                where = f"{campaign.id}/{p.id} block {i + 1}"
                check_source(where, b.source)
                if b.kind == "quote":
                    if normalize(b.text) not in normalize(doc(b.source.vignette) or ""):
                        rep.errors.append(f"{where}: quote not found verbatim in {b.source.vignette}: “{b.text[:90]}…”")
                    rep.checked += 1
                elif b.kind == "code":
                    check_snippet(where, b.text, b.source, allow_adapted=False)
    return rep


def write_index(pack: Pack, path: Path) -> None:
    pins = " and ".join(
        f"[`{p.repo}@{p.ref}`](https://github.com/{p.repo}/tree/{p.ref}/{p.path})" for p in pack.all_pins()
    )
    lines = [
        "# Sources",
        "",
        f"Every mission, quiz and notebook page in the **{pack.name}** pack cites the upstream "
        f"documentation at {pins}. "
        "`tools/verify_sources.py` checks that each quote and each line of solution code appears verbatim "
        "in the cited document. This file is generated by that tool; do not edit it by hand.",
        "",
    ]
    for c in pack.campaigns:
        lines += [f"## {c.title}", "", "| Item | Source | Section |", "|---|---|---|"]

        def row(label: str, src: Source) -> str:
            pin, document = pack.resolve_source(src.vignette)
            return (
                f"| {label} | [{document}]({pin.site_url(document)}) "
                f"([pinned]({pin.blob_url(document)})) | {src.section} |"
            )

        for m in c.missions:
            lines.append(row(f"Mission: {m.title}", m.source))
        for q in c.quizzes:
            lines.append(row(f"Quiz: {q.question}", q.source))
        for p in c.notebook:
            seen = set()
            for b in p.blocks:
                if b.source and (b.source.vignette, b.source.section) not in seen:
                    seen.add((b.source.vignette, b.source.section))
                    lines.append(row(f"Notebook: {p.title}", b.source))
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", default=str(ROOT / "packs" / "seurat"))
    parser.add_argument("--source-dir", help="local directory with the source documents (skips downloading)")
    parser.add_argument("--no-write", action="store_true", help="do not regenerate docs/SOURCES.md")
    args = parser.parse_args()
    pack = load_pack(args.pack)
    rep = verify(pack, Path(args.source_dir) if args.source_dir else None)
    for line in rep.adapted:
        print(f"adapted  {line}")
    for line in rep.errors:
        print(f"ERROR    {line}")
    pins = ", ".join(f"{p.repo}@{p.ref}" for p in pack.all_pins())
    print(f"\n{rep.checked} checks, {len(rep.errors)} errors, {len(rep.adapted)} adapted lines ({pins})")
    if not args.no_write:
        name = "SOURCES.md" if pack.id == "seurat" else f"SOURCES-{pack.id}.md"
        write_index(pack, ROOT / "docs" / name)
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
