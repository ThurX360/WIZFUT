from __future__ import annotations
import os, time, yaml
from dataclasses import dataclass
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from utils.logging_setup import setup_logger
from sources.futwiz_scraper import FutwizScraper, FutwizScraperConfig
from detectors.underpriced import detect_underpriced, UnderpricedConfig
from detectors.fake_bin import detect_fake_bin, FakeBinConfig
from detectors.spike import detect_spike, SpikeConfig
from notifier.discord_webhook import send_discord_message
from storage.state import AlertState
from storage.price_history import PriceHistory

load_dotenv()
log = setup_logger()

@dataclass
class Config:
    poll_interval_secs: int
    min_discount: float
    zscore_min: float
    fake_drop_pct: float
    spike_pct: float
    cooldown_minutes: int
    notify_discord: bool
    futwiz_platform: str
    futwiz_pages: int
    futwiz_delay_between_pages: float
    futwiz_delay_jitter: float
    futwiz_timeout: float
    futwiz_max_retries: int
    futwiz_backoff_factor: float
    futwiz_extra_headers: Dict[str, str]
    futwiz_proxies: Dict[str, str]
    history_window_minutes: int
    history_max_points: int
    history_min_points: int

def load_config() -> Config:
    path = "config.yaml"
    if not os.path.exists(path):
        log.warning("config.yaml não encontrado, usando config.example.yaml")
        path = "config.example.yaml"
    with open(path, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    futwiz_cfg = y.get("futwiz", {}) or {}
    history_cfg = y.get("history", {}) or {}
    return Config(
        poll_interval_secs=int(y.get("poll_interval_secs", 20)),
        min_discount=float(y.get("min_discount", 0.12)),
        zscore_min=float(y.get("zscore_min", 1.8)),
        fake_drop_pct=float(y.get("fake_drop_pct", 0.40)),
        spike_pct=float(y.get("spike_pct", 0.20)),
        cooldown_minutes=int(y.get("cooldown_minutes", 15)),
        notify_discord=bool(y.get("notify_discord", True)),
        futwiz_platform=str(futwiz_cfg.get("platform", "ps")),
        futwiz_pages=int(futwiz_cfg.get("pages", 1)),
        futwiz_delay_between_pages=float(futwiz_cfg.get("delay_between_pages", 1.0)),
        futwiz_delay_jitter=float(futwiz_cfg.get("delay_jitter", 0.0)),
        futwiz_timeout=float(futwiz_cfg.get("timeout", 15.0)),
        futwiz_max_retries=int(futwiz_cfg.get("max_retries", 3)),
        futwiz_backoff_factor=float(futwiz_cfg.get("backoff_factor", 0.5)),
        futwiz_extra_headers=dict(futwiz_cfg.get("extra_headers", {}) or {}),
        futwiz_proxies=dict(futwiz_cfg.get("proxies", {}) or {}),
        history_window_minutes=max(1, int(history_cfg.get("window_minutes", 60 * 24))),
        history_max_points=max(10, int(history_cfg.get("max_points", 400))),
        history_min_points=max(1, int(history_cfg.get("min_points", 3))),
    )

def fmt_coin(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        text = value.strip().replace(" ", "")
        if not text:
            return None
        if "." in text and "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif text.count(",") == 1 and "." not in text:
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") > 1 and "," not in text:
            text = text.replace(".", "")
        elif text.count(".") == 1 and "," not in text:
            left, right = text.split(".")
            if len(right) == 3 and len(left) >= 1:
                text = left + right
        text = text.replace(",", "")
        try:
            return float(text)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def format_alert(row: Dict[str, Any], info: Dict[str, Any]) -> str:
    badge = info.get("type","ALERT")
    name = row.get("name","?")
    rating = row.get("rating","?")
    price_raw = row.get("price", 0)
    price_val = _to_float(price_raw) or 0
    price = int(round(price_val)) if price_val else 0
    expected_raw = info.get("expected", price)
    expected_float = _to_float(expected_raw) or price
    expected = int(round(expected_float)) if expected_float else price
    history_points = info.get("history_points")
    history_suffix = (
        f" | Hist.: {history_points} pts" if isinstance(history_points, int) and history_points > 0 else ""
    )
    if badge == "UNDERPRICED":
        score = info.get('score')
        score_fmt = score if score is not None else "--"
        return (f"🟢 **UNDERPRICED** — {name} ({rating})\n"
                f"Preço: **{fmt_coin(price)}** | Esperado: {fmt_coin(expected)} "
                f"(desconto ~{int(info.get('discount_pct',0)*100)}%, z≈{score_fmt})"
                f"{history_suffix}")
    if badge == "FAKE_BIN_SUSPECT":
        return (f"🟠 **FAKE BIN?** — {name} ({rating})\n"
                f"Preço: **{fmt_coin(price)}** | Média: {fmt_coin(expected)} "
                f"(queda ~{int(info.get('drop_pct',0)*100)}%)"
                f"{history_suffix}")
    if badge == "SPIKE":
        return (f"🔵 **SPIKE** — {name} ({rating})\n"
                f"Preço: **{fmt_coin(price)}** | Média: {fmt_coin(expected)} "
                f"(alta ~{int(info.get('spike_pct',0)*100)}%)"
                f"{history_suffix}")
    return f"🔔 {badge} — {name} ({rating}) @ {fmt_coin(price)}"

def maybe_notify(cfg: Config, content: str):
    if not cfg.notify_discord:
        log.info("[ALERTA] " + content.replace("\n"," | "))
        return
    ok, err = send_discord_message(content)
    if not ok:
        log.warning(f"Falha ao enviar Discord: {err}")
    else:
        log.info("Alerta enviado ao Discord.")

def run():
    cfg = load_config()
    state = AlertState()
    history = PriceHistory(
        window_minutes=cfg.history_window_minutes,
        max_points=cfg.history_max_points,
    )
    log.info("Iniciando FC26 Market Watch")
    log.info(
        "Histórico interno: janela=%s min | max=%s pts | mínimo p/ usar=%s",
        cfg.history_window_minutes,
        cfg.history_max_points,
        cfg.history_min_points,
    )
    log.info(
        "Scraping Futwiz | plataforma: %s | páginas: %s",
        cfg.futwiz_platform,
        cfg.futwiz_pages,
    )
    log.info("Intervalo de pooling: %ss", cfg.poll_interval_secs)
    ucfg = UnderpricedConfig(cfg.min_discount, cfg.zscore_min)
    fcfg = FakeBinConfig(cfg.fake_drop_pct)
    scfg = SpikeConfig(cfg.spike_pct)
    cooldown = cfg.cooldown_minutes * 60

    scraper = FutwizScraper()
    scraper_cfg = FutwizScraperConfig(
        platform=cfg.futwiz_platform,
        pages=cfg.futwiz_pages,
        delay_between_pages=cfg.futwiz_delay_between_pages,
        delay_jitter=cfg.futwiz_delay_jitter,
        timeout=cfg.futwiz_timeout,
        max_retries=cfg.futwiz_max_retries,
        backoff_factor=cfg.futwiz_backoff_factor,
        extra_headers=cfg.futwiz_extra_headers,
        proxies=cfg.futwiz_proxies,
    )

    while True:
        try:
            rows = scraper.fetch_market(scraper_cfg)
            if not rows:
                log.warning("Scraper Futwiz não retornou dados")
                time.sleep(cfg.poll_interval_secs)
                continue
            log.info(
                f"{len(rows)} itens recebidos da Futwiz. Rodando detectores..."
            )

            for row in rows:
                pid = str(row.get("player_id") or row.get("name"))
                price_value = _to_float(row.get("price"))
                if price_value is None:
                    continue

                history.add(pid, price_value, row.get("updated_at"))
                stats = history.get_stats(pid)
                if stats and stats.count >= cfg.history_min_points:
                    if row.get("avg_price_24h") in (None, "", 0):
                        row["avg_price_24h"] = stats.average
                    if row.get("std_24h") in (None, ""):
                        row["std_24h"] = stats.stddev

                # Detectores
                for det_name, info in (
                    ("UNDERPRICED", detect_underpriced(row, ucfg)),
                    ("FAKE_BIN", detect_fake_bin(row, fcfg)),
                    ("SPIKE", detect_spike(row, scfg)),
                ):
                    if not info:
                        continue
                    if not state.can_alert(pid, det_name, cooldown):
                        continue
                    if stats and stats.count:
                        info.setdefault("history_points", stats.count)
                    content = format_alert(row, info)
                    maybe_notify(cfg, content)

        except KeyboardInterrupt:
            log.info("Encerrando...")
            break
        except Exception as e:
            log.exception(f"Erro no loop: {e}")

        time.sleep(cfg.poll_interval_secs)

if __name__ == "__main__":
    run()
