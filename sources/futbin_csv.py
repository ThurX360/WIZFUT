"""Reader utilities for Futbin style CSV exports."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

_EXPECTED_HEADERS = {
    "player_id",
    "name",
    "rating",
    "league",
    "position",
    "price",
    "avg_price_24h",
    "std_24h",
    "updated_at",
}


def _normalise_row(row: Dict[str, str]) -> Dict[str, object]:
    data: Dict[str, object] = {k: v for k, v in row.items()}

    for key in ("player_id", "rating"):
        value = data.get(key)
        if value is None or value == "":
            continue
        try:
            data[key] = int(float(value))
        except ValueError:
            pass

    for key in ("price", "avg_price_24h"):
        value = data.get(key)
        if value in (None, ""):
            continue
        try:
            data[key] = int(float(value))
        except ValueError:
            try:
                data[key] = float(value)
            except ValueError:
                pass

    value = data.get("std_24h")
    if value not in (None, ""):
        try:
            data["std_24h"] = float(value)
        except ValueError:
            pass

    value = data.get("updated_at")
    if isinstance(value, str) and value:
        try:
            data["updated_at"] = datetime.fromisoformat(value)
        except ValueError:
            pass

    return data


def read_rows(path: str | Path) -> List[Dict[str, object]]:
    """Read the Futbin CSV file and return normalised dictionaries."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = _EXPECTED_HEADERS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"CSV incompleto, cabeçalhos ausentes: {', '.join(sorted(missing))}"
            )
        return [_normalise_row(row) for row in reader]
