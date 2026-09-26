from __future__ import annotations

from pathlib import Path

import pytest

from curelab.balance import load_balance
from curelab.content import load_illness, load_pack
from curelab.game import Game

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURE_PACK = HERE / "fixtures" / "pack_py"
ILLNESSES = REPO / "illnesses"
SEURAT_PACK = REPO / "packs" / "seurat"


@pytest.fixture(scope="session")
def pack():
    return load_pack(FIXTURE_PACK)


@pytest.fixture(scope="session")
def balance():
    return load_balance()


@pytest.fixture(scope="session")
def nsclc():
    return load_illness(ILLNESSES, "nsclc")


@pytest.fixture(scope="session")
def neuroblastoma():
    return load_illness(ILLNESSES, "neuroblastoma")


@pytest.fixture
def game(pack, nsclc, balance):
    return Game.new(pack.campaign("demo-one"), nsclc, balance, "normal", seed=7)
