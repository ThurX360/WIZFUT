"""Simple in-memory state helpers."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class AlertState:
    """Track last alert timestamps for cooldown management."""

    last_alerts: Dict[Tuple[str, str], float] = field(default_factory=dict)

    def can_alert(self, player_id: str, detector: str, cooldown_seconds: int) -> bool:
        now = time.time()
        key = (player_id, detector)
        ts = self.last_alerts.get(key)
        if ts and (now - ts) < cooldown_seconds:
            return False
        self.last_alerts[key] = now
        return True
