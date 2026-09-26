from __future__ import annotations

import random

import pytest

from curelab.evolution import available_traits, evolve
from curelab.content import Illness
from curelab.game import Game, RuleError


def test_new_game_starts_healthy(game):
    s = game.state
    assert s.health == 100 and s.research == 0 and s.rp == 0 and s.status == "playing"
    assert s.timeline[0].kind == "admit"
    assert game.day == 1
    assert game.vitals()["hr"] == pytest.approx(86, abs=0.1)


def test_decline_is_slow_without_errors(game):
    game.advance(3600)  # one active hour, no errors
    assert 97 < game.state.health < 100
    assert game.day == 61


def test_errors_accelerate_decline(pack, nsclc, balance):
    calm = Game.new(pack.campaign("demo-one"), nsclc, balance, seed=1)
    rough = Game.new(pack.campaign("demo-one"), nsclc, balance, seed=1)
    for _ in range(20):
        rough.wrong_attempt("test")
    calm.advance(3600)
    rough.advance(3600)
    assert rough.severity > calm.severity
    assert rough.state.health < calm.state.health - 5


def test_patient_dies(game):
    for _ in range(80):
        game.wrong_attempt("test")
    game.advance(6 * 3600)
    assert game.state.status == "lost"
    assert game.state.health == 0
    assert game.state.stage == "deceased"
    assert game.vitals()["hr"] == 0
    assert game.state.events[-1].kind == "lost"
    with pytest.raises(RuleError):
        game.record_submission("demo-m01-list", True)


def test_evolution_respects_prerequisites_and_exclusions(nsclc, balance):
    rng = random.Random(3)
    acquired: list[str] = []
    for _ in range(len(nsclc.traits) + 5):
        evo = evolve(nsclc, acquired, balance, "normal", rng)
        if evo.trait is None:
            break
        assert set(evo.trait.requires) <= set(acquired)
        assert not set(evo.trait.excludes) & set(acquired)
        acquired.append(evo.trait.id)
    drivers = {"egfr", "kras_g12c", "alk_fusion"} & set(acquired)
    assert len(drivers) <= 1
    assert available_traits(nsclc, acquired) == []
    exhausted = evolve(nsclc, acquired, balance, "normal", rng)
    assert exhausted.trait is None and exhausted.gain > 0


def test_first_traits_are_roots(nsclc, balance):
    roots = {t.id for t in nsclc.traits if not t.requires}
    for seed in range(30):
        evo = evolve(nsclc, [], balance, "normal", random.Random(seed))
        assert evo.trait.id in roots


def test_wrong_attempt_event(game):
    ev = game.wrong_attempt("mission x")
    assert ev.kind == "trait"
    assert ev.data["gain"] > 0
    assert game.state.errors == 1
    assert game.state.traits[0].note in [t.text for t in game.state.timeline]


def test_missions_unlock_in_order(game):
    assert game.mission_status("demo-m01-list") == "available"
    assert game.mission_status("demo-m02-sum") == "locked"
    with pytest.raises(RuleError):
        game.record_submission("demo-m02-sum", True)
    events = game.record_submission("demo-m01-list", False)
    assert events[0].kind == "trait"
    events = game.record_submission("demo-m01-list", True)
    assert events[0].kind == "mission"
    assert game.state.research == 30
    assert game.mission_status("demo-m02-sum") == "available"
    p = game.state.missions["demo-m01-list"]
    assert (p.attempts, p.wrong, p.completed) == (2, 1, True)
    # completing twice does nothing
    assert game.record_submission("demo-m01-list", True) == []
    assert game.state.research == 30


def test_quiz_flow(game):
    with pytest.raises(RuleError):
        game.answer_quiz("demo-q01", 1)  # locked until mission 1
    game.record_submission("demo-m01-list", True)
    correct, events = game.answer_quiz("demo-q01", 0)
    assert not correct and events[0].kind == "trait"
    with pytest.raises(RuleError):
        game.answer_quiz("demo-q01", 0)  # already ruled out
    correct, events = game.answer_quiz("demo-q01", 1)
    assert correct and game.state.research == 35
    assert game.quiz_status("demo-q01") == "completed"


def test_win(game):
    for mid in ("demo-m01-list", "demo-m02-sum", "demo-m03-sort"):
        game.record_submission(mid, True)
    game.answer_quiz("demo-q01", 1)
    assert game.state.status == "playing"
    _, events = game.answer_quiz("demo-q02", 1)
    assert game.state.research == 100
    assert game.state.status == "won"
    assert events[-1].kind == "won"
    assert game.state.stage == "cured"
    game.advance(10 * 3600)  # no further decline after winning
    assert game.state.health > 0


def test_hints_cost_research_points(game):
    with pytest.raises(RuleError, match="research points"):
        game.buy_hint("demo-m01-list")
    ev = game.read_page("demo-nb01")
    assert ev.data["amount"] == 2 and game.state.rp == 2
    assert game.read_page("demo-nb01") is None  # once per page
    assert game.buy_hint("demo-m01-list") == 0
    assert game.buy_hint("demo-m01-list") == 1
    assert game.state.rp == 0 and game.state.rp_spent == 2
    with pytest.raises(RuleError):
        game.buy_hint("demo-m01-list")


def test_note_rewards_capped_by_missions_attempted(game):
    assert game.sync_note_rewards(3) is None  # nothing attempted yet
    game.record_submission("demo-m01-list", False)
    ev = game.sync_note_rewards(3)
    assert ev.data["amount"] == 1
    assert game.sync_note_rewards(3) is None
    game.record_submission("demo-m01-list", True)
    game.record_submission("demo-m02-sum", False)
    assert game.sync_note_rewards(3).data["amount"] == 1
    assert game.state.note_rp_awarded == 2
    # deleting notes never claws back RP, and re-adding does not double-pay
    assert game.sync_note_rewards(0) is None
    assert game.sync_note_rewards(2) is None


def test_stage_changes_are_logged(game):
    for _ in range(25):
        game.wrong_attempt("t")
    game.advance(2 * 3600)
    stages = [e for e in game.state.events if e.kind == "stage"]
    assert stages, "expected at least one stage change"
    assert game.state.stage in ("symptomatic", "serious", "critical", "deceased")


def test_difficulty_scales_creep(pack, nsclc, balance):
    casual = Game.new(pack.campaign("demo-one"), nsclc, balance, "casual", seed=1)
    brutal = Game.new(pack.campaign("demo-one"), nsclc, balance, "brutal", seed=1)
    casual.advance(3600)
    brutal.advance(3600)
    assert brutal.state.health < casual.state.health


# --------------------------------------------------------------------------- #
# Patient events: random, non-symptom things that happen on the ward
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("illness_name", ["nsclc", "neuroblastoma"])
def test_events_are_mixed_in_at_random(illness_name, balance, request):
    illness = request.getfixturevalue(illness_name)
    draws = [evolve(illness, [], balance, "normal", random.Random(seed)).trait for seed in range(800)]
    share = sum(t.is_event for t in draws) / len(draws)
    assert abs(share - balance.event_chance) < 0.05
    # every event can come up, not just a favourite few
    assert {t.id for t in draws if t.is_event} == {t.id for t in illness.traits if t.is_event}


@pytest.mark.parametrize("illness_name", ["nsclc", "neuroblastoma"])
def test_fewer_than_a_quarter_of_events_are_neutral(illness_name, request):
    illness = request.getfixturevalue(illness_name)
    events = [t for t in illness.traits if t.is_event]
    neutral = [t for t in events if t.neutral]
    assert len(events) >= 6
    assert 1 <= len(neutral) and len(neutral) * 4 < len(events)
    for t in events:
        assert not t.requires, "events happen at random, independent of the tree"


def test_neutral_event_costs_nothing_but_still_counts(pack, neuroblastoma, balance):
    for seed in range(2000):
        game = Game.new(pack.campaign("demo-two"), neuroblastoma, balance, seed=seed)
        ev = game.wrong_attempt("test")
        if ev.data.get("neutral"):
            break
    else:  # pragma: no cover
        pytest.fail("no neutral event drawn")
    assert ev.data["event"] and ev.data["gain"] == 0
    assert game.state.trait_severity == 0 and game.state.errors == 1
    assert game.state.timeline[-1].kind == "event"
    assert game.stats()["events"] == 1 and game.stats()["traits"] == 0


def test_harmful_event_raises_lethality(pack, nsclc, balance):
    for seed in range(2000):
        game = Game.new(pack.campaign("demo-one"), nsclc, balance, seed=seed)
        ev = game.wrong_attempt("test")
        if ev.data.get("event") and not ev.data.get("neutral"):
            break
    assert ev.data["gain"] > 0 and game.state.trait_severity > 0


def test_only_events_may_be_neutral(nsclc):
    data = nsclc.model_dump()
    cough = next(t for t in data["traits"] if t["id"] == "cough")
    cough["severity"] = (0, 0)
    with pytest.raises(ValueError, match="only patient events can be neutral"):
        Illness.model_validate(data)
