"""Lightweight HTML scraper for Futwiz player price tables."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)

_PRICE_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)([kmbKMB]?)")


@dataclass
class FutwizScraperConfig:
    platform: str = "ps"
    pages: int = 1
    delay_between_pages: float = 1.0


class FutwizScraper:
    """Small helper responsible for scraping Futwiz tables."""

    BASE_URL = "https://www.futwiz.com/en/fc24/players"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", _USER_AGENT)

    def _parse_coin(self, text: str) -> Optional[int]:
        text = (text or "").strip()
        if not text or text in {"-", "?"}:
            return None
        match = _PRICE_RE.search(text.replace(" ", ""))
        if not match:
            return None
        number = float(match.group(1).replace(",", ""))
        suffix = match.group(2).lower()
        if suffix == "k":
            number *= 1_000
        elif suffix == "m":
            number *= 1_000_000
        elif suffix == "b":
            number *= 1_000_000_000
        return int(number)

    def _parse_row(self, tr: Tag, platform: str) -> Optional[Dict[str, object]]:
        player_id = tr.get("data-playerid") or tr.get("data-id")
        cells = tr.find_all("td")
        if not cells:
            return None

        colmap: Dict[str, str] = {}
        for td in cells:
            key = (td.get("data-title") or td.get("data-th") or "").strip().lower()
            if key:
                colmap[key] = td.get_text(" ", strip=True)

        texts = [td.get_text(" ", strip=True) for td in cells]

        rating = colmap.get("rating") or (texts[0] if texts else None)
        name = colmap.get("name") or colmap.get("player")
        if name is None and len(texts) >= 2:
            name = texts[1]

        price_key_candidates = [
            f"price ({platform})",
            f"bin ({platform})",
            f"{platform} lowest",
            f"{platform} price",
            "price",
        ]
        price_text = None
        for key in price_key_candidates:
            if key in colmap:
                price_text = colmap[key]
                break
        if price_text is None and len(texts) >= 6:
            price_text = texts[5]

        avg_text = colmap.get("average") or colmap.get("24h avg")
        if avg_text is None and len(texts) >= 7:
            avg_text = texts[6]

        updated = colmap.get("updated") or colmap.get("last updated")

        try:
            rating_value = int(rating)
        except (TypeError, ValueError):
            rating_value = None

        price_value = self._parse_coin(price_text) if price_text else None
        avg_value = self._parse_coin(avg_text) if avg_text else None

        if not player_id and name:
            player_id = name.lower().replace(" ", "-")

        if not player_id or not name or not price_value:
            return None

        updated_at = datetime.now(timezone.utc)
        if updated:
            updated_at = datetime.now(timezone.utc)

        return {
            "player_id": player_id,
            "name": name,
            "rating": rating_value,
            "price": price_value,
            "avg_price_24h": avg_value or price_value,
            "std_24h": None,
            "updated_at": updated_at,
        }

    def _parse_page(self, html: str, platform: str) -> List[Dict[str, object]]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []
        rows: List[Dict[str, object]] = []
        for tr in table.find_all("tr"):
            data = self._parse_row(tr, platform)
            if data:
                rows.append(data)
        return rows

    def fetch_page(self, page: int, platform: str) -> str:
        response = self.session.get(
            self.BASE_URL,
            params={"page": page, "platform": platform},
            timeout=15,
        )
        response.raise_for_status()
        return response.text

    def fetch_market(self, cfg: FutwizScraperConfig) -> List[Dict[str, object]]:
        all_rows: List[Dict[str, object]] = []
        for page in range(1, cfg.pages + 1):
            html = self.fetch_page(page, cfg.platform)
            rows = self._parse_page(html, cfg.platform)
            if not rows:
                break
            all_rows.extend(rows)
            if cfg.delay_between_pages:
                time.sleep(cfg.delay_between_pages)
        return all_rows
