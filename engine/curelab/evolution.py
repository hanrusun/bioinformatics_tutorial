"""Trait-tree evolution: what the disease does after each wrong attempt."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Optional

from .balance import Balance
from .content import Illness, Trait


@dataclass(frozen=True)
class Evolution:
    trait: Optional[Trait]  # None once the tree is exhausted ("further progression")
    gain: float


def available_traits(illness: Illness, acquired: Iterable[str]) -> list[Trait]:
    have = set(acquired)
    blocked = {x for t in illness.traits if t.id in have for x in t.excludes}
    return [
        t
        for t in illness.traits
        if t.id not in have
        and t.id not in blocked
        and set(t.requires) <= have
        and not (set(t.excludes) & have)
    ]


def evolve(
    illness: Illness,
    acquired: Iterable[str],
    balance: Balance,
    difficulty: str,
    rng: random.Random,
) -> Evolution:
    """Pick what happens after a wrong attempt, and its severity gain.

    With probability ``event_chance`` a random, not-yet-seen patient event is
    drawn (the patient starts smoking, swallows a crayon, ...); events have no
    place in the tree and some are neutral. Otherwise the disease itself
    evolves: candidates are traits whose prerequisites are all met, weighted
    by ``1 / tier ** tier_weight_exponent`` so early mistakes tend to produce
    mild symptoms and severe complications come later. If one pool is empty
    the other is used; once both are empty the disease simply progresses.

    The gain is drawn uniformly from the trait's range, then scaled by
    ``gain_scale`` and the difficulty's ``gain_mult`` (neutral events stay 0).
    """
    diff = balance.difficulty(difficulty)
    mult = balance.gain_scale * diff.gain_mult
    candidates = available_traits(illness, acquired)
    events = [t for t in candidates if t.is_event]
    disease = [t for t in candidates if not t.is_event]
    if not candidates:
        lo, hi = balance.exhausted_gain
        return Evolution(trait=None, gain=rng.uniform(lo, hi) * diff.gain_mult)
    if events and (not disease or rng.random() < balance.event_chance):
        trait = rng.choice(events)
    else:
        weights = [1.0 / (t.tier ** balance.tier_weight_exponent) for t in disease]
        trait = rng.choices(disease, weights=weights, k=1)[0]
    lo, hi = trait.severity
    return Evolution(trait=trait, gain=0.0 if trait.neutral else rng.uniform(lo, hi) * mult)
