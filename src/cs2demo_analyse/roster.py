from __future__ import annotations

from collections import defaultdict
from datetime import date

from .config import COUNTED_ROSTER_STATUSES
from .io_utils import parse_date
from .models import RosterInterval


def load_roster_intervals(rows: list[dict[str, str]]) -> list[RosterInterval]:
    intervals: list[RosterInterval] = []
    for row in rows:
        player = (row.get("Player") or "").strip()
        steam64 = (row.get("SteamID") or row.get("steam64") or "").strip()
        start_raw = (row.get("Start") or "").strip()
        status = (row.get("Status") or "").strip()
        if not player or not steam64 or not start_raw or not status:
            continue
        end_raw = (row.get("End") or "").strip()
        intervals.append(
            RosterInterval(
                player=player,
                steam64=steam64,
                start=parse_date(start_raw),
                end=parse_date(end_raw) if end_raw else None,
                status=status,
            )
        )
    return intervals


def is_counted_status(status: str) -> bool:
    return status.strip().lower() in COUNTED_ROSTER_STATUSES


class RosterBook:
    def __init__(self, intervals: list[RosterInterval]) -> None:
        self._by_player: dict[str, list[RosterInterval]] = defaultdict(list)
        self._by_steam: dict[str, list[RosterInterval]] = defaultdict(list)
        for interval in intervals:
            self._by_player[interval.player].append(interval)
            self._by_steam[interval.steam64].append(interval)

    def is_active_player(self, player: str, day: date) -> bool:
        for interval in self._by_player.get(player, []):
            if is_counted_status(interval.status) and interval.contains(day):
                return True
        return False

    def status_for(self, player: str, day: date) -> str | None:
        for interval in self._by_player.get(player, []):
            if is_counted_status(interval.status) and interval.contains(day):
                return interval.status
        return None

    def active_identity_for_steam(self, steam64: str, day: date) -> tuple[str, str] | None:
        for interval in self._by_steam.get(steam64, []):
            if is_counted_status(interval.status) and interval.contains(day):
                return interval.player, interval.status
        return None
