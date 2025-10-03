"""Discord webhook notification helper."""
from __future__ import annotations

import os
from typing import Tuple

import requests


DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def send_discord_message(content: str) -> Tuple[bool, str | None]:
    """Send ``content`` to the configured Discord webhook.

    Returns a tuple ``(ok, error_message)``.  When the webhook URL is not set
    the function returns ``(False, "Webhook não configurado")``.
    """

    if not DISCORD_WEBHOOK_URL:
        return False, "Webhook não configurado"

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": content},
            timeout=10,
        )
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}: {response.text[:200]}"
        return True, None
    except requests.RequestException as exc:  # pragma: no cover - network failures
        return False, str(exc)
