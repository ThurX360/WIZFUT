"""Spike detector."""
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
class SpikeConfig:
    spike_pct: float


def detect_spike(row: Dict[str, Any], cfg: SpikeConfig) -> Optional[Dict[str, Any]]:
    price = _to_int(row.get("price"))
    avg = _to_float(row.get("avg_price_24h"))
    if not price or not avg:
        return None

    spike = (price / avg) - 1
    if spike < cfg.spike_pct:
        return None

    return {
        "type": "SPIKE",
        "spike_pct": spike,
        "expected": avg,
    }
