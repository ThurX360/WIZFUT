"""In-memory helper to accumulate price history statistics."""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, Optional, Tuple


@dataclass
class PriceStats:
    """Aggregated metrics for a player's price history."""

    average: float
    stddev: float
    count: int


@dataclass
class PriceHistory:
    """Maintain rolling price histories per player."""

    window_minutes: int = 60 * 24
    max_points: int = 400
    _data: Dict[str, Deque[Tuple[float, float]]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.window_seconds = max(60, int(self.window_minutes) * 60)
        self.max_points = max(10, int(self.max_points))

    def _normalise_timestamp(self, value: object | None) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.timestamp()
        if isinstance(value, str) and value:
            text = value.strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                return time.time()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        return time.time()

    def _trim(self, series: Deque[Tuple[float, float]], now: float) -> None:
        cutoff = now - self.window_seconds
        while series and series[0][0] < cutoff:
            series.popleft()
        while len(series) > self.max_points:
            series.popleft()

    def add(self, player_id: str, price: float, updated_at: object | None = None) -> None:
        """Add a new price sample for ``player_id``."""

        ts = self._normalise_timestamp(updated_at)
        series = self._data.setdefault(player_id, deque())
        series.append((ts, float(price)))
        self._trim(series, ts)

    def get_stats(self, player_id: str) -> Optional[PriceStats]:
        """Return aggregated stats for ``player_id`` within the window."""

        series = self._data.get(player_id)
        if not series:
            return None

        now = time.time()
        self._trim(series, now)
        if not series:
            return None

        prices = [price for _, price in series]
        count = len(prices)
        if not count:
            return None

        avg = sum(prices) / count
        if count == 1:
            stddev = 0.0
        else:
            variance = sum((price - avg) ** 2 for price in prices) / count
            stddev = math.sqrt(variance)
        return PriceStats(average=avg, stddev=stddev, count=count)

    def clear(self) -> None:
        """Remove all cached history."""

        self._data.clear()
