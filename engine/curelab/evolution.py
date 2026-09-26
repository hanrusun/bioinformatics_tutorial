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
    """Pick the next trait and its severity gain.

    Candidates are traits whose prerequisites are all met. They are weighted by
    ``1 / tier ** tier_weight_exponent`` so early mistakes tend to produce mild
    symptoms and severe complications appear later in the tree. The gain is
    drawn uniformly from the trait's range, then scaled by ``gain_scale`` and
    the difficulty's ``gain_mult``.
    """
    mult = balance.gain_scale * balance.difficulty(difficulty).gain_mult
    candidates = available_traits(illness, acquired)
    if not candidates:
        lo, hi = balance.exhausted_gain
        return Evolution(trait=None, gain=rng.uniform(lo, hi) * balance.difficulty(difficulty).gain_mult)
    weights = [1.0 / (t.tier ** balance.tier_weight_exponent) for t in candidates]
    trait = rng.choices(candidates, weights=weights, k=1)[0]
    lo, hi = trait.severity
    return Evolution(trait=trait, gain=rng.uniform(lo, hi) * mult)
