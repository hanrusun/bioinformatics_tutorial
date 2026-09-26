from __future__ import annotations

import shutil

import pytest
import yaml

from curelab.content import ContentError, Illness, NotebookBlock, Quiz, load_illness, load_pack

from .conftest import FIXTURE_PACK, ILLNESSES


def test_fixture_pack_loads(pack):
    assert pack.id == "demo-python"
    assert [c.id for c in pack.campaigns] == ["demo-one", "demo-two"]
    one = pack.campaign("demo-one")
    assert [m.id for m in one.missions] == ["demo-m01-list", "demo-m02-sum", "demo-m03-sort"]
    assert one.total_points == 100
    assert pack.campaign("demo-two").unlock_after == "demo-one"


def test_source_urls(pack):
    pin = pack.source_pin
    assert pin.raw_url("introduction.rst") == (
        "https://raw.githubusercontent.com/python/cpython/v3.12.0/Doc/tutorial/introduction.rst"
    )
    assert pin.site_url("introduction.rst") == "https://docs.python.org/3/tutorial/introduction.html"


@pytest.mark.parametrize("illness_id", ["nsclc", "neuroblastoma"])
def test_real_illnesses_load(illness_id):
    illness = load_illness(ILLNESSES, illness_id)
    assert illness.patient.name
    assert len(illness.traits) >= 15
    # every overlay key is a simple identifier the art manifest can map
    for t in illness.traits:
        assert t.overlay is None or t.overlay.replace("_", "").isalnum()
        assert "{" not in illness.fill(t.note)


def test_fill_leaves_code_braces(nsclc):
    text = nsclc.fill("{name} runs `function(x) { x }` and {unknown}")
    assert text.startswith("Walter runs")
    assert "{ x }" in text and "{unknown}" in text


def test_quiz_validation():
    base = dict(id="q", after="m", question="?", explanation="", source={"vignette": "v", "section": "s"})
    with pytest.raises(ValueError):
        Quiz.model_validate({**base, "choices": ["a", "b"], "answer": 2})
    with pytest.raises(ValueError):
        Quiz.model_validate({**base, "choices": ["a", "a"], "answer": 0})


def test_notebook_block_shorthand():
    b = NotebookBlock.model_validate({"quote": "hi", "source": {"vignette": "v", "section": "s"}})
    assert b.kind == "quote"
    with pytest.raises(ValueError):
        NotebookBlock.model_validate({"code": "x <- 1"})  # code without a source


def test_trait_cycle_detected(nsclc):
    data = nsclc.model_dump()
    data["traits"][0]["requires"] = [data["traits"][5]["id"]]  # cough requires dyspnea -> cycle
    with pytest.raises(ValueError, match="cycle"):
        Illness.model_validate(data)


def test_unknown_quiz_reference_rejected(tmp_path):
    dst = tmp_path / "pack"
    shutil.copytree(FIXTURE_PACK, dst)
    qpath = dst / "campaigns" / "demo-one" / "quizzes.yaml"
    quizzes = yaml.safe_load(qpath.read_text())
    quizzes[0]["after"] = "nope"
    qpath.write_text(yaml.safe_dump(quizzes))
    with pytest.raises(ContentError, match="unknown mission"):
        load_pack(dst)
