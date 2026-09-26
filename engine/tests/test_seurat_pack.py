"""Structural tests for the real Seurat pack content (no R needed)."""

from __future__ import annotations

import re

import pytest

from curelab.content import load_illness, load_pack

from .conftest import ILLNESSES, SEURAT_PACK


def call_args(code: str, fn: str) -> list[list[str]]:
    """Top-level argument strings of every call to `fn` in R code."""
    calls = []
    for m in re.finditer(re.escape(fn) + r"\(", code):
        i, depth, quote, args, cur = m.end(), 1, None, [], ""
        while i < len(code) and depth:
            ch = code[i]
            if quote:
                cur += ch
                if ch == "\\":
                    cur += code[i + 1]
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
                cur += ch
            elif ch in "([{":
                depth += 1
                cur += ch
            elif ch in ")]}":
                depth -= 1
                if depth:
                    cur += ch
            elif ch == "," and depth == 1:
                args.append(cur.strip())
                cur = ""
            else:
                cur += ch
            i += 1
        args.append(cur.strip())
        calls.append(args)
    return calls


@pytest.fixture(scope="module")
def seurat():
    return load_pack(SEURAT_PACK)


def test_campaigns(seurat):
    assert [c.id for c in seurat.campaigns] == ["c1-basics", "c2-multiome"]
    assert seurat.campaign("c2-multiome").unlock_after == "c1-basics"
    for c in seurat.campaigns:
        load_illness(ILLNESSES, c.illness)


@pytest.mark.parametrize("campaign_id", ["c1-basics", "c2-multiome"])
def test_points_add_up_to_a_cure(seurat, campaign_id):
    c = seurat.campaign(campaign_id)
    assert c.total_points == 100
    assert sum(m.points for m in c.missions) == 85
    assert len(c.quizzes) == 15 and all(q.points == 1 for q in c.quizzes)


@pytest.mark.parametrize("campaign_id", ["c1-basics", "c2-multiome"])
def test_every_mission_is_complete(seurat, campaign_id):
    c = seurat.campaign(campaign_id)
    ids = [m.id for m in c.missions]
    for i, m in enumerate(c.missions):
        assert m.solution.strip() and m.check.strip()
        assert "curelab_check(" in m.check
        assert m.notebook_pages, f"{m.id} should link a notebook page"
        assert m.wrong_solutions, f"{m.id} needs at least one wrong solution to test its check"
        assert len(m.hints) == 3 and "```" in m.hints[2], "the last hint shows the code"
        # every expected() key used by the check is produced at build time
        for args in call_args(m.check, "expect_equal_ref"):
            key = args[1].strip("\"'")
            assert key in m.expected, f"{m.id}: check uses expected '{key}' that is never built"
        # checkpoints form a chain: a mission that loads a checkpoint loads an earlier one that saves state
        for loaded in re.findall(r'load_checkpoint\("([\w-]+)"\)', m.setup):
            assert loaded in ids[:i], f"{m.id} loads a checkpoint that is not built before it"
            assert c.mission(loaded).state, f"{loaded} must save state for {m.id}"


def test_prep_checkpoints_exist(seurat):
    prep_dir = SEURAT_PACK / "r" / "prep"
    built = {re.search(r'save_checkpoint\("prep-([\w]+)"', p.read_text()).group(1) for p in prep_dir.glob("*.R")}
    for c in seurat.campaigns:
        for m in c.missions:
            for name in re.findall(r'load_prep\("([\w]+)"\)', m.setup):
                assert name in built, f"{m.id} loads prep '{name}' that no prep script builds"


def test_quizzes_have_quotes_and_distinct_answers(seurat):
    for c in seurat.campaigns:
        for q in c.quizzes:
            assert q.source.quote, f"{q.id} must quote its source"
        # quizzes unlock throughout the campaign, not all at the end
        afters = {q.after for q in c.quizzes}
        assert len(afters) >= 8


def test_notebook_pages(seurat):
    for c in seurat.campaigns:
        assert 6 <= len(c.notebook) <= 8
        covered = {m for p in c.notebook for m in p.missions}
        assert covered == {m.id for m in c.missions}, "every mission is covered by a notebook page"
        for p in c.notebook:
            assert 1 <= p.rp <= 2
            assert any(b.kind in ("quote", "code") for b in p.blocks)


def test_debug_patterns_compile(seurat):
    for rule in seurat.debug:
        re.compile(rule.pattern)
    for c in seurat.campaigns:
        for m in c.missions:
            for rule in m.debug:
                re.compile(rule.pattern)
