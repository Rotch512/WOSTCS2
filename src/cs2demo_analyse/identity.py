from __future__ import annotations

import csv
from pathlib import Path

from .io_utils import ensure_dir, write_csv_dicts
from .models import PlayerIdentity


IDENTITY_FIELDS = ["steam64", "canonical_player", "enabled", "notes"]


def read_identities(path: Path) -> dict[str, PlayerIdentity]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        identities: dict[str, PlayerIdentity] = {}
        for row in rows:
            steam64 = (row.get("steam64") or "").strip()
            if not steam64:
                continue
            enabled_raw = (row.get("enabled") or "").strip().lower()
            enabled = enabled_raw in {"1", "true", "yes", "y", "是"}
            identities[steam64] = PlayerIdentity(
                steam64=steam64,
                canonical_player=(row.get("canonical_player") or "").strip(),
                enabled=enabled,
                notes=(row.get("notes") or "").strip(),
            )
        return identities


def write_identity_template(path: Path, discovered: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    existing = read_identities(path)
    rows: list[dict[str, str]] = []
    for item in discovered:
        steam64 = str(item.get("steam64", "")).strip()
        current = existing.get(steam64)
        rows.append({
            "steam64": steam64,
            "canonical_player": current.canonical_player if current else "",
            "enabled": "true" if current and current.enabled else "false",
            "notes": current.notes if current else f"names={', '.join(item.get('names', []))}",
        })
    write_csv_dicts(path, rows, IDENTITY_FIELDS)

