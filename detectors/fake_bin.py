"""Fake BIN detector."""
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
class FakeBinConfig:
    fake_drop_pct: float


def detect_fake_bin(row: Dict[str, Any], cfg: FakeBinConfig) -> Optional[Dict[str, Any]]:
    price = _to_int(row.get("price"))
    avg = _to_float(row.get("avg_price_24h"))
    std = _to_float(row.get("std_24h")) or 0.0

    if not price or not avg:
        return None

    drop_pct = 1 - (price / avg)
    if drop_pct < cfg.fake_drop_pct:
        return None

    if std > 0 and drop_pct < (cfg.fake_drop_pct + 0.05):
        # Quando existe desvio considerável o alerta tende a ser ruído
        return None

    return {
        "type": "FAKE_BIN_SUSPECT",
        "drop_pct": drop_pct,
        "expected": avg,
    }
