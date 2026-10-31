"""Run configuration: scale presets, fixed seed and planning calendar.

Every scale uses the SAME generator code; only these numbers change
(requirement: "parameterize scale so starter and full datasets use the same generator").
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta

DEFAULT_SEED = 20261022
PLAN_YEAR = 2026
# Planning "as-of" date = Monday of ISO week 2026-W01. All event history is
# dated on/before this date; everything after it is a forecast or a plan.
AS_OF = date.fromisocalendar(PLAN_YEAR, 1, 1)  # 2025-12-29
GENERATOR_VERSION = "1.0.0"


@dataclass(frozen=True)
class ScaleConfig:
    name: str
    n_skus: int
    n_locations: int
    n_weeks: int
    n_suppliers: int
    n_purchase_orders: int          # baseline inbound orders (PO headers)
    anomalies_per_type: int         # labelled edge cases injected per issue type

    def to_dict(self) -> dict:
        return asdict(self)


SCALES: dict[str, ScaleConfig] = {
    # tiny: used by the automated tests (runs in a few seconds)
    "tiny": ScaleConfig("tiny", 150, 6, 52, 25, 400, 4),
    # starter: small dataset that is committed to the repo for reviewers
    "starter": ScaleConfig("starter", 300, 10, 52, 50, 1000, 8),
    # full: the volume requested in the brief
    "full": ScaleConfig("full", 3000, 50, 52, 500, 10000, 40),
}


def get_scale(name: str, **overrides) -> ScaleConfig:
    if name not in SCALES:
        raise ValueError(f"unknown scale '{name}', choose from {sorted(SCALES)}")
    cfg = SCALES[name]
    clean = {k: v for k, v in overrides.items() if v is not None}
    if clean:
        cfg = replace(cfg, name=f"{name}-custom", **clean)
    if not 1 <= cfg.n_weeks <= 52:
        raise ValueError("n_weeks must be between 1 and 52")
    return cfg


def week_start(i: int) -> date:
    """Monday of planning week index i (0-based)."""
    return AS_OF + timedelta(days=7 * i)


def week_id(i: int) -> str:
    return f"{PLAN_YEAR}W{i + 1:02d}"
