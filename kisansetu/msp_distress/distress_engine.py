"""Dynamic MSP Floor calculation engine.

Standalone math module. No database or FastAPI imports — copy this file
into any Python backend and call the functions directly.

Formulas
--------
P_MSP_Quality = P_MSP * Q_m
    Q_m = 1.10 Grade A, 1.00 Grade B, 0.85 Grade C

C_holding = (C_storage_daily * t_days) + T_logistics

F_dynamic = P_MSP_Quality + C_holding

Distress trigger
----------------
is_distress if P_mandi_predicted < P_MSP  OR  P_current_offer < F_dynamic
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

QUALITY_MULTIPLIERS = {
    "A": 1.10,
    "GRADE A": 1.10,
    "GRADE_A": 1.10,
    "B": 1.00,
    "GRADE B": 1.00,
    "GRADE_B": 1.00,
    "C": 0.85,
    "GRADE C": 0.85,
    "GRADE_C": 0.85,
}

DWR_LOAN_LTV = 0.70


class DistressEngineError(ValueError):
    """Raised when floor inputs are invalid."""


def quality_multiplier(grade: str) -> float:
    """Return Q_m for a Computer-Vision quality grade."""
    key = str(grade or "B").strip().upper()
    if key not in QUALITY_MULTIPLIERS:
        raise DistressEngineError(
            f"Unknown quality grade '{grade}'. Use A, B or C."
        )
    return QUALITY_MULTIPLIERS[key]


def effective_quality_adjusted_msp(p_msp: float, quality_grade: str) -> float:
    """P_MSP-Quality = P_MSP * Q_m (per kg)."""
    if p_msp < 0:
        raise DistressEngineError("P_MSP cannot be negative.")
    return round(float(p_msp) * quality_multiplier(quality_grade), 4)


def total_holding_expense(
    storage_daily_per_kg: float,
    holding_days: float,
    logistics_per_kg: float,
) -> float:
    """C_holding = (C_storage_daily * t_days) + T_logistics (per kg)."""
    if storage_daily_per_kg < 0 or holding_days < 0 or logistics_per_kg < 0:
        raise DistressEngineError("Holding cost inputs cannot be negative.")
    return round(
        (float(storage_daily_per_kg) * float(holding_days))
        + float(logistics_per_kg),
        4,
    )


def dynamic_msp_floor(
    p_msp: float,
    quality_grade: str = "B",
    storage_daily_per_kg: float = 0.0,
    holding_days: float = 0.0,
    logistics_per_kg: float = 0.0,
) -> float:
    """F_dynamic = P_MSP-Quality + C_holding (per kg). Non-negotiable baseline."""
    p_quality = effective_quality_adjusted_msp(p_msp, quality_grade)
    c_holding = total_holding_expense(
        storage_daily_per_kg, holding_days, logistics_per_kg
    )
    return round(p_quality + c_holding, 4)


def is_distress_condition(
    p_mandi_predicted: float,
    p_msp: float,
    p_current_offer: Optional[float] = None,
    f_dynamic: Optional[float] = None,
) -> bool:
    """True when forecasted mandi price is below MSP or offer is below F_dynamic."""
    if p_mandi_predicted < p_msp:
        return True
    if p_current_offer is not None and f_dynamic is not None:
        if p_current_offer < f_dynamic:
            return True
    return False


def bid_meets_floor(bid_per_kg: float, f_dynamic: float) -> bool:
    """Reverse bids must be >= F_dynamic."""
    return float(bid_per_kg) + 1e-9 >= float(f_dynamic)


def dwr_loan_advance(crop_value: float, ltv: float = DWR_LOAN_LTV) -> float:
    """Instant cash advance against stored crop value (default 70% LTV)."""
    if crop_value < 0:
        raise DistressEngineError("Crop value cannot be negative.")
    if not 0 <= ltv <= 1:
        raise DistressEngineError("LTV must be between 0 and 1.")
    return round(float(crop_value) * float(ltv), 2)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    from math import radians, sin, cos, asin, sqrt

    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return round(2 * r * asin(sqrt(a)), 2)


def logistics_from_distance(distance_km: float, rate_per_kg_per_km: float = 0.012) -> float:
    """Estimate T_logistics per kg from road distance."""
    if distance_km < 0 or rate_per_kg_per_km < 0:
        raise DistressEngineError("Distance / rate cannot be negative.")
    return round(float(distance_km) * float(rate_per_kg_per_km), 4)


@dataclass
class FloorBreakdown:
    """Transparent cost sheet shown to farmers and out-of-zone buyers."""

    p_msp: float
    quality_grade: str
    q_m: float
    p_msp_quality: float
    storage_daily_per_kg: float
    holding_days: float
    logistics_per_kg: float
    c_holding: float
    f_dynamic: float
    p_mandi_predicted: float
    p_current_offer: Optional[float]
    is_distress: bool
    trigger_reasons: list

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_floor(
    p_msp: float,
    quality_grade: str,
    p_mandi_predicted: float,
    storage_daily_per_kg: float = 0.0,
    holding_days: float = 0.0,
    logistics_per_kg: float = 0.0,
    p_current_offer: Optional[float] = None,
) -> FloorBreakdown:
    """Run the full Dynamic MSP Floor pipeline and return a breakdown."""
    q_m = quality_multiplier(quality_grade)
    p_quality = effective_quality_adjusted_msp(p_msp, quality_grade)
    c_holding = total_holding_expense(
        storage_daily_per_kg, holding_days, logistics_per_kg
    )
    f_dyn = round(p_quality + c_holding, 4)
    reasons = []
    if p_mandi_predicted < p_msp:
        reasons.append("P_mandi_predicted < P_MSP")
    if p_current_offer is not None and p_current_offer < f_dyn:
        reasons.append("P_current_offer < F_dynamic")
    distressed = bool(reasons)
    print(
        f"[MSP-ENGINE] grade={quality_grade} Qm={q_m} P_MSP={p_msp} "
        f"P_quality={p_quality} C_holding={c_holding} F_dynamic={f_dyn} "
        f"P_forecast={p_mandi_predicted} distress={distressed}"
    )
    return FloorBreakdown(
        p_msp=round(float(p_msp), 4),
        quality_grade=str(quality_grade).upper(),
        q_m=q_m,
        p_msp_quality=p_quality,
        storage_daily_per_kg=round(float(storage_daily_per_kg), 4),
        holding_days=float(holding_days),
        logistics_per_kg=round(float(logistics_per_kg), 4),
        c_holding=c_holding,
        f_dynamic=f_dyn,
        p_mandi_predicted=round(float(p_mandi_predicted), 4),
        p_current_offer=None if p_current_offer is None else round(float(p_current_offer), 4),
        is_distress=distressed,
        trigger_reasons=reasons,
    )
