from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_FOLDER_ID = "1sleUCIdrDyZEtZnwu84zr8s2TVrXM_DO"
REPLAYS_DATA_FOLDER_ID = "1nQ-IeHvFiuDiGI-onjeX_cclHV4yi321"
REPLAYS_FILTER_SHEET_ID = "1FqP2Ae0Nzt1kAvW1Iz_yPk5FVI0tqmj5Hjpsp6_ANUQ"
ROSTER_SHEET_ID = "1HPHNXr5r4e9y9ecgTcIJCtkuW8u8OUJOwBNbyzAw3qk"

REPLAYS_FILTER_TAB = "data"
ROSTER_TAB = "Data"
ANALYSIS_MANIFEST_NAME = "analysis_manifest.json"

COUNTED_ROSTER_STATUSES = {"starter", "stand-in", "standin", "benched"}


@dataclass(frozen=True)
class Settings:
    output_dir: Path = Path("output")
    cache_dir: Path = Path(".cache/cs2demo")
    replays_filter_sheet_id: str = REPLAYS_FILTER_SHEET_ID
    roster_sheet_id: str = ROSTER_SHEET_ID
    replays_filter_tab: str = REPLAYS_FILTER_TAB
    roster_tab: str = ROSTER_TAB

    @property
    def sheets_dir(self) -> Path:
        return self.output_dir / "sheets"

    @property
    def packages_dir(self) -> Path:
        return self.cache_dir / "packages"

    @property
    def demos_dir(self) -> Path:
        return self.cache_dir / "demos"

    @property
    def discovered_players_path(self) -> Path:
        return self.output_dir / "discovered_players.json"

    @property
    def identity_path(self) -> Path:
        return self.output_dir / "player_identity.csv"

    @property
    def summary_path(self) -> Path:
        return self.output_dir / "summary.json"

    @property
    def player_match_stats_path(self) -> Path:
        return self.output_dir / "player_match_stats.json"

    @property
    def errors_path(self) -> Path:
        return self.output_dir / "errors.json"

    @property
    def sheet_versions_path(self) -> Path:
        return self.output_dir / "sheet_versions.json"

    @property
    def demo_manifest_path(self) -> Path:
        return self.output_dir / "demo_manifest.json"
