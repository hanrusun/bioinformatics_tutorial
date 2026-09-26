from __future__ import annotations

from curelab.game import GameState
from curelab.notebook import Note, Notebook, export_markdown, qualifying_notes, word_count
from curelab.store import Profile, Store


def test_word_count():
    assert word_count("") == 0
    assert word_count("NormalizeData() scales counts; log1p(x) then x10,000.") == 6
    assert word_count("percent.mt < 5 & nFeature_RNA > 200") == 4


def test_qualifying_notes():
    nb = Notebook(notes=[Note(body="word " * 39), Note(body="word " * 40), Note(body="")])
    assert qualifying_notes(nb, 40) == 1


def test_export_scopes(pack, nsclc, game):
    campaign = pack.campaign("demo-one")
    nb = Notebook(notes=[Note(title="QC thoughts", body="Mito reads flag dying cells.")])
    game.read_page("demo-nb01")
    game.record_submission("demo-m01-list", True)
    everything = export_markdown(pack, campaign, nsclc, nb, "all", game)
    mine = export_markdown(pack, campaign, nsclc, nb, "mine", game)
    assert "# Reference pages" in everything and "## Lists" in everything
    assert "✓ Read" in everything
    assert "# Mission log" in everything and "Collect the samples" in everything
    assert "# Patient chart" in everything
    assert "Source: introduction.rst" in everything
    assert "QC thoughts" in mine and "Mito reads flag dying cells." in mine
    assert "# Reference pages" not in mine and "Mission log" not in mine


def test_store_roundtrip(tmp_path, game):
    store = Store(tmp_path)
    profile = Profile(active=game.state, won=["x"])
    profile.notebook("demo-one").notes.append(Note(title="t", body="b"))
    store.save(profile)
    loaded = store.load()
    assert loaded.won == ["x"]
    assert isinstance(loaded.active, GameState)
    assert loaded.active.seed == game.state.seed
    assert loaded.notebooks["demo-one"].notes[0].title == "t"


def test_store_survives_corrupt_file(tmp_path):
    (tmp_path / "profile.json").write_text("{not json")
    store = Store(tmp_path)
    assert store.load().active is None
    assert (tmp_path / "profile.corrupt.json").exists()
