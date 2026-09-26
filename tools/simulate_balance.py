#!/usr/bin/env python3
"""Monte-Carlo balance check for Cure Lab.

Simulated players work through a campaign using the real engine
(`curelab.game.Game`), the real illness trait trees and `balance.yaml`:

* idle      - never makes progress or mistakes; how long does the patient live?
* careful   - no mistakes
* typical   - ~2 wrong submissions per average mission, the odd wrong quiz answer, ~3 h
* reckless  - ~5 wrong submissions per average mission (~80 errors), ~3 h

Mission time and mistakes scale with the mission's points, which the packs
already assign by complexity.

Usage:
    python tools/simulate_balance.py            # print a report
    python tools/simulate_balance.py --assert   # exit 1 if targets are missed
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from curelab.balance import Balance, load_balance  # noqa: E402
from curelab.content import Campaign, Illness, Mission, Quiz, Source, load_illness, load_pack  # noqa: E402
from curelab.game import Game  # noqa: E402


@dataclass
class Profile:
    name: str
    errors_per_point: float  # Poisson mean of wrong submissions per mission point
    quiz_errors: float  # Poisson mean per quiz (capped at choices-1)
    minutes_per_point: tuple[float, float]
    quiz_minutes: tuple[float, float] = (0.5, 1.5)


PROFILES = {
    "careful": Profile("careful", 0.0, 0.0, (0.9, 1.9)),
    "typical": Profile("typical", 0.3, 0.35, (1.1, 2.3)),
    "reckless": Profile("reckless", 0.8, 0.8, (1.1, 2.3)),
}


def synthetic_campaign(illness_id: str, n_missions: int = 13, n_quizzes: int = 15) -> Campaign:
    src = Source(vignette="x", section="x")
    per = 85 // n_missions
    points = [per] * n_missions
    points[-1] += 85 - sum(points)
    missions = [
        Mission(id=f"m{i}", title=f"m{i}", points=p, source=src, briefing="", task=[], solution="", check="", hints=["a", "b", "c"])
        for i, p in enumerate(points)
    ]
    quizzes = [
        Quiz(id=f"q{i}", after=missions[min(i * n_missions // n_quizzes, n_missions - 1)].id, question="?",
             choices=["a", "b", "c", "d"], answer=0, explanation="", source=src)
        for i in range(n_quizzes)
    ]
    return Campaign(id=f"synthetic-{illness_id}", title="synthetic", illness=illness_id, missions=missions, quizzes=quizzes)


def campaigns() -> list[Campaign]:
    pack_dir = ROOT / "packs" / "seurat"
    if (pack_dir / "pack.yaml").exists():
        return load_pack(pack_dir).campaigns
    return [synthetic_campaign("nsclc", 13), synthetic_campaign("neuroblastoma", 11)]


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    # Knuth's algorithm is fine for small lambda
    limit, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def play(campaign: Campaign, illness: Illness, balance: Balance, profile: Profile, seed: int, difficulty: str = "normal") -> Game:
    rng = random.Random(seed)
    game = Game.new(campaign, illness, balance, difficulty, seed=seed)
    quizzes_after: dict[str, list[Quiz]] = {}
    for q in campaign.quizzes:
        quizzes_after.setdefault(q.after, []).append(q)

    def spend(seconds: float, errors: int, action) -> None:
        marks = sorted(rng.uniform(0, seconds) for _ in range(errors))
        t = 0.0
        for m in marks:
            game.advance(m - t)
            t = m
            if game.state.status != "playing":
                return
            action()
        game.advance(seconds - t)

    for mission in campaign.missions:
        if game.state.status != "playing":
            break
        minutes = rng.uniform(*profile.minutes_per_point) * mission.points
        errors = poisson(rng, profile.errors_per_point * mission.points)
        spend(minutes * 60, errors, lambda: game.record_submission(mission.id, False))
        if game.state.status != "playing":
            break
        game.record_submission(mission.id, True)
        for quiz in quizzes_after.get(mission.id, []):
            if game.state.status != "playing":
                break
            wrong = [i for i in range(len(quiz.choices)) if i != quiz.answer]
            rng.shuffle(wrong)
            n_wrong = min(len(wrong), poisson(rng, profile.quiz_errors))
            wrong_iter = iter(wrong[:n_wrong])
            spend(rng.uniform(*profile.quiz_minutes) * 60, n_wrong, lambda: game.answer_quiz(quiz.id, next(wrong_iter)))
            if game.state.status == "playing":
                game.answer_quiz(quiz.id, quiz.answer)
    return game


def idle_survival_hours(campaign: Campaign, illness: Illness, balance: Balance, difficulty: str = "normal") -> float:
    game = Game.new(campaign, illness, balance, difficulty, seed=1)
    while game.state.status == "playing" and game.state.clock < 48 * 3600:
        game.advance(60)
    return game.state.clock / 3600


def report(n: int, check: bool) -> bool:
    balance = load_balance()
    targets = balance.targets
    ok = True
    illness_dir = ROOT / "illnesses"
    for campaign in campaigns():
        illness = load_illness(illness_dir, campaign.illness)
        print(f"\n== {campaign.id} ({illness.name}, {len(campaign.missions)} missions, {len(campaign.quizzes)} quizzes)")
        for difficulty in balance.difficulties:
            idle = idle_survival_hours(campaign, illness, balance, difficulty)
            print(f"  [{difficulty}] idle patient survives {idle:.1f} h of active play")
            if difficulty == "normal" and targets and idle < targets.idle_survival_hours_min:
                print(f"    FAIL idle survival < {targets.idle_survival_hours_min} h")
                ok = False
        for name, profile in PROFILES.items():
            games = [play(campaign, illness, balance, profile, seed) for seed in range(n)]
            wins = sum(g.state.status == "won" for g in games) / n
            healths = [g.state.health for g in games]
            errors = [g.state.errors for g in games]
            hours = [g.state.clock / 3600 for g in games]
            med_h = statistics.median(healths)
            print(
                f"  {name:8s} win {wins:5.1%}  median health {med_h:5.1f}  "
                f"errors {statistics.mean(errors):5.1f}  time {statistics.mean(hours):4.2f} h"
            )
            if not targets:
                continue
            if name == "careful" and med_h < targets.careful_final_health_min:
                print(f"    FAIL careful median health < {targets.careful_final_health_min}")
                ok = False
            if name == "typical":
                lo, hi = targets.typical_median_health
                if wins < targets.typical_win_rate_min:
                    print(f"    FAIL typical win rate < {targets.typical_win_rate_min:.0%}")
                    ok = False
                if not lo <= med_h <= hi:
                    print(f"    FAIL typical median health outside [{lo}, {hi}]")
                    ok = False
            if name == "reckless" and 1 - wins < targets.reckless_loss_rate_min:
                print(f"    FAIL reckless loss rate < {targets.reckless_loss_rate_min:.0%}")
                ok = False
    print("\nOK: all balance targets met" if ok else "\nBalance targets missed")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assert", dest="check", action="store_true", help="exit non-zero if targets are missed")
    parser.add_argument("-n", type=int, default=200, help="simulated players per profile")
    args = parser.parse_args()
    ok = report(args.n, args.check)
    if args.check and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
