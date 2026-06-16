from __future__ import annotations

from .io_utils import parse_date
from .models import ReplayRecord


def load_replays(rows: list[dict[str, str]]) -> list[ReplayRecord]:
    replays: list[ReplayRecord] = []
    for row in rows:
        file_id = (row.get("file_id") or row.get("ID") or "").strip()
        file_url = (row.get("file_url") or row.get("URL") or "").strip()
        if not file_id:
            continue
        replays.append(
            ReplayRecord(
                file_id=file_id,
                file_url=file_url,
                match_date=parse_date(row.get("match_date") or row.get("Date") or ""),
                map_name=(row.get("map_name") or row.get("Map Name") or "").strip().lower(),
                roster_type=(row.get("roster_type") or row.get("Roster Type") or "").strip().lower(),
                match_result=(row.get("match_result") or row.get("Match Result") or "").strip().lower(),
                our_score=int(row.get("our_score") or row.get("Our Score") or "0"),
                opponent_score=int(row.get("opponent_score") or row.get("Opponent Score") or "0"),
            )
        )
    return replays

