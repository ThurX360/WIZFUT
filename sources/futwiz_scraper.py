"""Lightweight HTML scraper for Futwiz player price tables."""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)

_PRICE_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)([kmbKMB]?)")
_RELATIVE_TIME_RE = re.compile(
    r"(?P<value>\d+)\s*(?P<unit>second|minute|hour|day|week)s?\s*ago",
    re.IGNORECASE,
)

log = logging.getLogger(__name__)


@dataclass
class FutwizScraperConfig:
    platform: str = "ps"
    pages: int = 1
    delay_between_pages: float = 1.0
    delay_jitter: float = 0.0
    timeout: float = 15.0
    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_statuses: Tuple[int, ...] = (429, 500, 502, 503, 504)
    extra_headers: Optional[Dict[str, str]] = None
    proxies: Optional[Dict[str, str]] = None


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

        data_price_value: Optional[int] = None
        for td in cells:
            if data_price_value is not None:
                break
            direct_attr = td.get("data-price")
            platform_attr = td.get(f"data-price-{platform}")
            raw_value = platform_attr or direct_attr
            if raw_value:
                data_price_value = self._parse_coin(raw_value)

        data_avg_value: Optional[int] = None
        for td in cells:
            if data_avg_value is not None:
                break
            direct_attr = td.get("data-average") or td.get("data-avg")
            raw_value = direct_attr
            if raw_value:
                data_avg_value = self._parse_coin(raw_value)

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

        price_value = data_price_value or (self._parse_coin(price_text) if price_text else None)
        avg_value = data_avg_value or (self._parse_coin(avg_text) if avg_text else None)

        if not player_id and name:
            player_id = name.lower().replace(" ", "-")

        if not player_id or not name or not price_value:
            return None

        updated_at = self._parse_updated(updated)

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

    def _configure_session(self, cfg: FutwizScraperConfig) -> None:
        retry = Retry(
            total=cfg.max_retries,
            backoff_factor=cfg.backoff_factor,
            status_forcelist=cfg.retry_statuses,
            allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if cfg.extra_headers:
            self.session.headers.update(cfg.extra_headers)
        if cfg.proxies:
            self.session.proxies.update(cfg.proxies)

    def _parse_updated(self, text: Optional[str]) -> datetime:
        if not text:
            return datetime.now(timezone.utc)

        normalized = text.strip().lower()
        if normalized in {"just now", "now", "-"}:
            return datetime.now(timezone.utc)

        match = _RELATIVE_TIME_RE.search(normalized)
        if match:
            value = int(match.group("value"))
            unit = match.group("unit").lower()
            delta_kwargs = {
                "second": "seconds",
                "minute": "minutes",
                "hour": "hours",
                "day": "days",
                "week": "weeks",
            }
            key = delta_kwargs.get(unit, "minutes")
            delta = timedelta(**{key: value})
            return datetime.now(timezone.utc) - delta

        for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%H:%M"):
            try:
                parsed = datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue
            else:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed

        return datetime.now(timezone.utc)

    def fetch_page(self, page: int, platform: str, timeout: float) -> str:
        response = self.session.get(
            self.BASE_URL,
            params={"page": page, "platform": platform},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.text

    def fetch_market(self, cfg: FutwizScraperConfig) -> List[Dict[str, object]]:
        self._configure_session(cfg)
        all_rows: List[Dict[str, object]] = []
        for page in range(1, cfg.pages + 1):
            try:
                html = self.fetch_page(page, cfg.platform, cfg.timeout)
            except RequestException as exc:
                log.warning("Falha ao baixar página %s (%s): %s", page, cfg.platform, exc)
                break
            rows = self._parse_page(html, cfg.platform)
            if not rows:
                break
            all_rows.extend(rows)
            if cfg.delay_between_pages or cfg.delay_jitter:
                base_delay = max(cfg.delay_between_pages, 0.0)
                jitter = random.uniform(-cfg.delay_jitter, cfg.delay_jitter) if cfg.delay_jitter else 0.0
                delay = max(0.0, base_delay + jitter)
                if delay:
                    time.sleep(delay)
        return all_rows
