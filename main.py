
from __future__ import annotations
import os, time, yaml, math
from dataclasses import dataclass
from typing import Dict, Any
from dotenv import load_dotenv

from utils.logging_setup import setup_logger
from sources.futbin_csv import read_rows
from detectors.underpriced import detect_underpriced, UnderpricedConfig
from detectors.fake_bin import detect_fake_bin, FakeBinConfig
from detectors.spike import detect_spike, SpikeConfig
from notifier.discord_webhook import send_discord_message
from storage.state import AlertState

load_dotenv()
log = setup_logger()

@dataclass
class Config:
    data_path: str
    poll_interval_secs: int
    min_discount: float
    zscore_min: float
    fake_drop_pct: float
    spike_pct: float
    cooldown_minutes: int
    notify_discord: bool

def load_config() -> Config:
    path = "config.yaml"
    if not os.path.exists(path):
        log.warning("config.yaml não encontrado, usando config.example.yaml")
        path = "config.example.yaml"
    with open(path, "r", encoding="utf-8") as f:
        y = yaml.safe_load(f)
    return Config(
        data_path=y.get("data_path","./data/futbin_export.csv"),
        poll_interval_secs=int(y.get("poll_interval_secs", 20)),
        min_discount=float(y.get("min_discount", 0.12)),
        zscore_min=float(y.get("zscore_min", 1.8)),
        fake_drop_pct=float(y.get("fake_drop_pct", 0.40)),
        spike_pct=float(y.get("spike_pct", 0.20)),
        cooldown_minutes=int(y.get("cooldown_minutes", 15)),
        notify_discord=bool(y.get("notify_discord", True)),
    )

def fmt_coin(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def format_alert(row: Dict[str, Any], info: Dict[str, Any]) -> str:
    badge = info.get("type","ALERT")
    name = row.get("name","?")
    rating = row.get("rating","?")
    price = int(float(row.get("price",0)))
    expected = int(info.get("expected", price))
    if badge == "UNDERPRICED":
        return (f"🟢 **UNDERPRICED** — {name} ({rating})\n"
                f"Preço: **{fmt_coin(price)}** | Esperado: {fmt_coin(expected)} "
                f"(desconto ~{int(info.get('discount_pct',0)*100)}%, z≈{info.get('score',0)})")
    if badge == "FAKE_BIN_SUSPECT":
        return (f"🟠 **FAKE BIN?** — {name} ({rating})\n"
                f"Preço: **{fmt_coin(price)}** | Média: {fmt_coin(expected)} "
                f"(queda ~{int(info.get('drop_pct',0)*100)}%)")
    if badge == "SPIKE":
        return (f"🔵 **SPIKE** — {name} ({rating})\n"
                f"Preço: **{fmt_coin(price)}** | Média: {fmt_coin(expected)} "
                f"(alta ~{int(info.get('spike_pct',0)*100)}%)")
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
    log.info("Iniciando FC26 Market Watch")
    log.info(f"Lendo: {cfg.data_path} | intervalo: {cfg.poll_interval_secs}s")
    ucfg = UnderpricedConfig(cfg.min_discount, cfg.zscore_min)
    fcfg = FakeBinConfig(cfg.fake_drop_pct)
    scfg = SpikeConfig(cfg.spike_pct)
    cooldown = cfg.cooldown_minutes * 60

    last_mtime = 0.0

    while True:
        try:
            if not os.path.exists(cfg.data_path):
                log.warning(f"Arquivo não encontrado: {cfg.data_path}")
                time.sleep(cfg.poll_interval_secs)
                continue

            mtime = os.path.getmtime(cfg.data_path)
            if mtime <= last_mtime:
                time.sleep(cfg.poll_interval_secs)
                continue
            last_mtime = mtime

            rows = read_rows(cfg.data_path)
            log.info(f"{len(rows)} linhas lidas. Rodando detectores...")

            for row in rows:
                pid = str(row.get("player_id") or row.get("name"))
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
