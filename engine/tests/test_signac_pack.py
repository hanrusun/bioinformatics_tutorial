"""Structural tests for the Signac pack (no R needed)."""

from __future__ import annotations

import re

import pytest

from curelab.content import load_illness, load_pack

from .conftest import ILLNESSES, SIGNAC_PACK
from .test_seurat_pack import call_args


@pytest.fixture(scope="module")
def signac():
    return load_pack(SIGNAC_PACK)


def test_campaigns_and_illness(signac):
    assert [c.id for c in signac.campaigns] == ["s1-multiome"]
    for c in signac.campaigns:
        load_illness(ILLNESSES, c.illness)


def test_cites_signac_and_seurat_vignettes(signac):
    repos = {signac.resolve_source(src.vignette)[0].repo for src in signac.sources()}
    assert repos == {"stuart-lab/signac", "satijalab/seurat"}
    assert signac.source_pin.ref == signac.tool_version == "1.17.1"


def test_helpers_build_on_the_seurat_pack(signac):
    init = signac.render_init()
    seurat_line, signac_line = init.strip().splitlines()
    assert "seurat/r/helpers.R" in seurat_line and signac_line.endswith('/r/helpers.R")')


def test_points_add_up_to_a_cure(signac):
    for c in signac.campaigns:
        assert c.total_points == 100
        assert sum(m.points for m in c.missions) == 85
        assert len(c.quizzes) == 15 and all(q.points == 1 for q in c.quizzes)
        assert len({q.after for q in c.quizzes}) >= 8


def test_every_mission_is_complete(signac):
    for c in signac.campaigns:
        ids = [m.id for m in c.missions]
        for i, m in enumerate(c.missions):
            assert m.solution.strip() and "curelab_check(" in m.check
            assert m.notebook_pages and m.wrong_solutions
            assert len(m.hints) == 3 and "```" in m.hints[2]
            for args in call_args(m.check, "expect_equal_ref"):
                key = args[1].strip("\"'")
                assert key in m.expected, f"{m.id}: check uses expected '{key}' that is never built"
            for loaded in re.findall(r'load_checkpoint\("([\w-]+)"\)', m.setup):
                assert loaded in ids[:i], f"{m.id} loads a checkpoint that is not built before it"
                assert c.mission(loaded).state, f"{loaded} must save state for {m.id}"


def test_notebook_covers_every_mission(signac):
    for c in signac.campaigns:
        assert 6 <= len(c.notebook) <= 8
        assert {m for p in c.notebook for m in p.missions} == {m.id for m in c.missions}


def test_debug_patterns_compile(signac):
    for rule in signac.debug:
        re.compile(rule.pattern)
    for c in signac.campaigns:
        for m in c.missions:
            for rule in m.debug:
                re.compile(rule.pattern)
