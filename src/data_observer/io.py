"""Small, dependency-free file adapters."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def read_csv(path: str | Path) -> tuple[list[dict[str, str | None]], tuple[str, ...]]:
    """Read a UTF-8 CSV, normalizing blank cells to ``None``."""

    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {source}")
        rows = [
            {key: value if value not in ("", None) else None for key, value in row.items()}
            for row in reader
        ]
    return rows, tuple(reader.fieldnames)


def read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
