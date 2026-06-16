from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ReplayRecord:
    file_id: str
    file_url: str
    match_date: date
    map_name: str
    roster_type: str
    match_result: str
    our_score: int
    opponent_score: int

    @property
    def match_id(self) -> str:
        return self.file_id

    @property
    def quarter(self) -> str:
        q = (self.match_date.month - 1) // 3 + 1
        return f"{self.match_date.year}-Q{q}"


@dataclass(frozen=True)
class RosterInterval:
    player: str
    steam64: str
    start: date
    end: date | None
    status: str

    def contains(self, day: date) -> bool:
        if day < self.start:
            return False
        if self.end is not None and day >= self.end:
            return False
        return True


@dataclass
class PlayerDiscovery:
    steam64: str
    names: set[str] = field(default_factory=set)
    first_seen: date | None = None
    last_seen: date | None = None
    demos: set[str] = field(default_factory=set)
    maps: set[str] = field(default_factory=set)
    team_names: set[str] = field(default_factory=set)

    def add(self, name: str, replay: ReplayRecord, team_name: str | None = None) -> None:
        clean_name = (name or "").strip()
        if clean_name:
            self.names.add(clean_name)
        self.demos.add(replay.match_id)
        self.maps.add(replay.map_name)
        if team_name:
            self.team_names.add(str(team_name))
        if self.first_seen is None or replay.match_date < self.first_seen:
            self.first_seen = replay.match_date
        if self.last_seen is None or replay.match_date > self.last_seen:
            self.last_seen = replay.match_date


@dataclass(frozen=True)
class PlayerIdentity:
    steam64: str
    canonical_player: str
    enabled: bool
    notes: str = ""


@dataclass
class PlayerMatchStats:
    steam64: str
    name: str
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    damage: int = 0
    rounds: int = 0
    opening_kills: int = 0
    opening_kill_round_wins: int = 0
    opening_deaths: int = 0
    opening_death_round_wins: int = 0
    trade_kills: int = 0
    flash_assists: int = 0
    flashes_thrown: int = 0
    opponent_flashed_count: int = 0
    opponent_flashed_time: float = 0.0
    teammate_flashed_count: int = 0
    teammate_flashed_time: float = 0.0
    utility_damage: int = 0
    he_damage: int = 0
    fire_damage: int = 0
    multi_kill_rounds: int = 0
    clutch_attempts: int = 0
    clutch_wins: int = 0
    clutch_losses: int = 0
    clutch_broad_attempts: int = 0
    clutch_broad_wins: int = 0
    clutch_broad_losses: int = 0
    clutch_rounds: list[dict[str, object]] = field(default_factory=list)
    clutch_failures: list[dict[str, object]] = field(default_factory=list)
    kast_rounds: int = 0
    headshot_kills: int = 0
    survived_rounds: int = 0
    rounds_won: int = 0
    kills_in_round_wins: int = 0
    damage_in_round_wins: int = 0
    rounds_with_kill: int = 0
    traded_deaths: int = 0
    opening_deaths_traded: int = 0
    support_rounds: int = 0
    assisted_kills: int = 0
    utility_kills: int = 0
    sniper_kills: int = 0
    sniper_multi_kill_rounds: int = 0
    sniper_opening_kills: int = 0
    pistol_rounds: int = 0
    pistol_kills: int = 0
    pistol_deaths: int = 0
    pistol_assists: int = 0
    pistol_damage: int = 0
    pistol_kast_rounds: int = 0
    side_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    advantage_failures: list[dict[str, object]] = field(default_factory=list)
    round_details: list[dict[str, object]] = field(default_factory=list)
