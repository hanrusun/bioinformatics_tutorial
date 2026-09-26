"""Patient model: vitals derived from health, severity and evolved traits."""

from __future__ import annotations

from typing import Iterable

from .content import VITAL_KEYS, Illness

# How far each vital drifts from baseline as health falls from 100 to 0.
_DECLINE_DRIFT = {
    "hr": 38.0,  # tachycardia
    "rr": 12.0,  # tachypnoea
    "spo2": -9.0,
    "sbp": -22.0,
    "dbp": -14.0,
    "temp": 0.9,
}

_LIMITS = {
    "hr": (30.0, 210.0),
    "rr": (6.0, 60.0),
    "spo2": (60.0, 100.0),
    "sbp": (60.0, 220.0),
    "dbp": (30.0, 140.0),
    "temp": (34.0, 41.5),
}


def vitals(illness: Illness, health: float, trait_ids: Iterable[str], status: str = "playing") -> dict[str, float]:
    """Current vital signs.

    Baseline vitals come from the illness file. As health falls, vitals drift
    toward a sicker profile; each evolved trait adds its own ``vitals`` offsets
    (e.g. neuroblastoma "hypertension" raises blood pressure). A cured patient
    returns to healthy-looking numbers; a deceased patient flatlines.
    """
    base = illness.patient.baseline_vitals.model_dump()
    if status == "lost" or health <= 0:
        return {"hr": 0.0, "rr": 0.0, "spo2": 0.0, "sbp": 0.0, "dbp": 0.0, "temp": round(base["temp"] - 1.5, 1)}
    if status == "won":
        return {k: round(v, 1) for k, v in base.items()}
    decline = max(0.0, min(1.0, (100.0 - health) / 100.0))
    out = {}
    for key in VITAL_KEYS:
        value = base[key] + _DECLINE_DRIFT[key] * decline
        for tid in trait_ids:
            value += illness.trait(tid).vitals.get(key, 0.0)
        lo, hi = _LIMITS[key]
        out[key] = round(max(lo, min(hi, value)), 1)
    return out
