"""Underpriced detector."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


@dataclass
class UnderpricedConfig:
    min_discount: float
    zscore_min: float


def detect_underpriced(row: Dict[str, Any], cfg: UnderpricedConfig) -> Optional[Dict[str, Any]]:
    price = _to_int(row.get("price"))
    avg = _to_float(row.get("avg_price_24h"))
    std = _to_float(row.get("std_24h"))

    if not price or not avg:
        return None

    discount = 1 - (price / avg)
    if discount < cfg.min_discount:
        return None

    score = None
    if std and std > 0:
        score = (price - avg) / std
        if score > -cfg.zscore_min:
            return None

    return {
        "type": "UNDERPRICED",
        "discount_pct": discount,
        "score": round(score, 2) if score is not None else None,
        "expected": avg,
    }
