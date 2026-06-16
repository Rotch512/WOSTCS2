from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import PlayerMatchStats, ReplayRecord


COUNT_FIELDS = (
    "rounds",
    "rounds_won",
    "kills",
    "kills_in_round_wins",
    "deaths",
    "assists",
    "damage",
    "damage_in_round_wins",
    "opening_kills",
    "opening_kill_round_wins",
    "opening_deaths",
    "opening_death_round_wins",
    "trade_kills",
    "traded_deaths",
    "opening_deaths_traded",
    "flash_assists",
    "flashes_thrown",
    "opponent_flashed_count",
    "opponent_flashed_time",
    "teammate_flashed_count",
    "teammate_flashed_time",
    "utility_damage",
    "he_damage",
    "fire_damage",
    "utility_kills",
    "multi_kill_rounds",
    "clutch_attempts",
    "clutch_wins",
    "clutch_losses",
    "clutch_broad_attempts",
    "clutch_broad_wins",
    "clutch_broad_losses",
    "kast_rounds",
    "headshot_kills",
    "survived_rounds",
    "rounds_with_kill",
    "support_rounds",
    "assisted_kills",
    "sniper_kills",
    "sniper_multi_kill_rounds",
    "sniper_opening_kills",
    "pistol_rounds",
    "pistol_kills",
    "pistol_deaths",
    "pistol_assists",
    "pistol_damage",
    "pistol_kast_rounds",
)

SIDE_NAMES = ("Both", "CT", "T")
DETAIL_LIST_FIELDS = ("advantage_failures", "clutch_rounds", "clutch_failures", "round_details")


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score(value: float, average: float, elite: float, reverse: bool = False) -> int:
    if reverse:
        raw = 50 + (average - value) / max(average - elite, 0.001) * 50
    else:
        raw = 50 + (value - average) / max(elite - average, 0.001) * 50
    return round(clamp(raw))


def grade(value: float, average: float, elite: float, reverse: bool = False) -> str:
    grade_score = score(value, average, elite, reverse)
    if grade_score >= 82:
        return "Elite"
    if grade_score >= 66:
        return "Good"
    if grade_score >= 48:
        return "Okay"
    if grade_score >= 32:
        return "Below avg."
    return "Poor"


def empty_counts() -> dict[str, Any]:
    return {field: 0 for field in COUNT_FIELDS}


def empty_aggregate(key: dict[str, str]) -> dict[str, Any]:
    return {
        **key,
        "matches": 0,
        **empty_counts(),
        "advantage_failures": [],
        "clutch_rounds": [],
        "clutch_failures": [],
        "side_stats": {side: empty_counts() for side in ("CT", "T")},
    }


def _add_counts(row: dict[str, Any], stats: PlayerMatchStats) -> None:
    row["matches"] += 1
    for field in COUNT_FIELDS:
        row[field] += getattr(stats, field, 0) or 0
    row.setdefault("advantage_failures", []).extend(getattr(stats, "advantage_failures", []) or [])
    row.setdefault("clutch_rounds", []).extend(getattr(stats, "clutch_rounds", []) or [])
    row.setdefault("clutch_failures", []).extend(getattr(stats, "clutch_failures", []) or [])
    existing_rounds = {
        (item.get("round"), item.get("side"))
        for item in row.setdefault("round_details", [])
        if isinstance(item, dict)
    }
    for item in getattr(stats, "round_details", []) or []:
        if not isinstance(item, dict):
            continue
        key = (item.get("round"), item.get("side"))
        if key in existing_rounds:
            continue
        row["round_details"].append(item)
        existing_rounds.add(key)
    for side in ("CT", "T"):
        side_source = (stats.side_stats or {}).get(side, {})
        side_target = row["side_stats"].setdefault(side, empty_counts())
        for field in COUNT_FIELDS:
            side_target[field] += side_source.get(field, 0) or 0


def _compute_from_counts(row: dict[str, Any]) -> dict[str, Any]:
    rounds = row["rounds"]
    kills = row["kills"]
    deaths = row["deaths"]
    assists = row["assists"]
    damage = row["damage"]
    opening_attempts_count = row["opening_kills"] + row["opening_deaths"]

    row["kd"] = round(safe_div(kills, deaths), 3)
    row["kpr"] = round(safe_div(kills, rounds), 3)
    row["dpr"] = round(safe_div(deaths, rounds), 3)
    row["apr"] = round(safe_div(assists, rounds), 3)
    row["adr"] = round(safe_div(damage, rounds), 1)
    row["kast"] = round(100 * safe_div(row["kast_rounds"], rounds), 1)
    row["survival_rate"] = round(100 * safe_div(row["survived_rounds"], rounds), 1)
    row["headshot_rate"] = round(100 * safe_div(row["headshot_kills"], kills), 1)
    row["opening_duel_diff"] = row["opening_kills"] - row["opening_deaths"]
    row["opening_kills_per_round"] = round(safe_div(row["opening_kills"], rounds), 3)
    row["opening_deaths_per_round"] = round(safe_div(row["opening_deaths"], rounds), 3)
    row["opening_attempts"] = round(100 * safe_div(opening_attempts_count, rounds), 1)
    row["opening_success"] = round(100 * safe_div(row["opening_kills"], opening_attempts_count), 1)
    row["opening_deaths_traded_percentage"] = round(100 * safe_div(row["opening_deaths_traded"], row["opening_deaths"]), 1)
    row["win_after_opening_kill"] = round(100 * safe_div(row["opening_kill_round_wins"], row["opening_kills"]), 1)
    row["multi_kill_rate"] = round(100 * safe_div(row["multi_kill_rounds"], rounds), 1)
    row["rounds_with_kill_percentage"] = round(100 * safe_div(row["rounds_with_kill"], rounds), 1)
    row["kills_per_round_win"] = round(safe_div(row["kills_in_round_wins"], row["rounds_won"]), 3)
    row["damage_per_round_win"] = round(safe_div(row["damage_in_round_wins"], row["rounds_won"]), 1)
    row["flash_assists_per_round"] = round(safe_div(row["flash_assists"], rounds), 3)
    row["utility_damage_per_round"] = round(safe_div(row["utility_damage"], rounds), 2)
    row["utility_kills_per_100_rounds"] = round(100 * safe_div(row["utility_kills"], rounds), 2)
    row["trade_kills_per_round"] = round(safe_div(row["trade_kills"], rounds), 3)
    row["trade_kills_percentage"] = round(100 * safe_div(row["trade_kills"], kills), 1)
    row["traded_deaths_per_round"] = round(safe_div(row["traded_deaths"], rounds), 3)
    row["traded_deaths_percentage"] = round(100 * safe_div(row["traded_deaths"], deaths), 1)
    row["saved_by_teammate_per_round"] = row["traded_deaths_per_round"]
    row["saved_teammate_per_round"] = row["trade_kills_per_round"]
    row["assisted_kills_percentage"] = round(100 * safe_div(row["assisted_kills"], kills), 1)
    row["support_rounds_percentage"] = round(100 * safe_div(row["support_rounds"], rounds), 1)
    row["damage_per_kill"] = round(safe_div(damage, kills), 1)
    row["attacks_per_round"] = round(safe_div(opening_attempts_count + row["rounds_with_kill"], rounds), 2)
    row["sniper_kills_per_round"] = round(safe_div(row["sniper_kills"], rounds), 3)
    row["sniper_kills_percentage"] = round(100 * safe_div(row["sniper_kills"], kills), 1)
    row["rounds_with_sniper_kills_percentage"] = round(100 * safe_div(row["sniper_kills"], rounds), 1)
    row["sniper_multi_kill_rounds_rate"] = round(safe_div(row["sniper_multi_kill_rounds"], rounds), 4)
    row["sniper_opening_kills_per_round"] = round(safe_div(row["sniper_opening_kills"], rounds), 4)
    row["pistol_rating"] = round(_rating_proxy({
        **row,
        "rounds": row["pistol_rounds"],
        "kills": row["pistol_kills"],
        "deaths": row["pistol_deaths"],
        "assists": row["pistol_assists"],
        "damage": row["pistol_damage"],
        "kast_rounds": row["pistol_kast_rounds"],
        "multi_kill_rounds": 0,
        "opening_kills": 0,
        "opening_deaths": 0,
        "trade_kills": 0,
    }), 3)
    row["clutch_points_per_round"] = round(safe_div(row["clutch_wins"], rounds), 3)
    row["clutch_win_rate"] = round(100 * safe_div(row["clutch_wins"], row.get("clutch_attempts", 0)), 1)
    row["last_alive_percentage"] = round(100 * safe_div(row["survived_rounds"], max(rounds - row["rounds_won"], 1)), 1) if rounds != row["rounds_won"] else 0.0
    row["one_on_one_win_percentage"] = 0.0
    row["time_alive_per_round_seconds"] = round(115 * safe_div(row["survived_rounds"], rounds) + 35 * safe_div(deaths, rounds), 1)
    row["saves_per_round_loss"] = round(100 * safe_div(row["survived_rounds"], max(rounds - row["rounds_won"], 1)), 1) if rounds != row["rounds_won"] else 0.0
    row["flashes_thrown_per_round"] = round(safe_div(row["flashes_thrown"], rounds), 3)
    row["time_opponent_flashed_per_round"] = round(safe_div(row["opponent_flashed_time"], rounds), 2)

    row["kill_rating"] = safe_div(row["kpr"], 0.68)
    row["damage_rating"] = safe_div(row["adr"], 75)
    row["survival_rating"] = safe_div(1 - row["dpr"], 0.34)
    row["kast_rating"] = safe_div(row["kast"] / 100, 0.73)
    row["multi_kill_rating"] = safe_div(safe_div(row["multi_kill_rounds"], rounds), 0.12)
    row["round_swing"] = round(
        100
        * (
            0.55 * safe_div(row["opening_duel_diff"], rounds)
            + 0.25 * safe_div(row["clutch_wins"], rounds)
            + 0.20 * safe_div(row["trade_kills"], rounds)
        ),
        2,
    )
    row["rws"] = round(max(0.0, 10 + row["round_swing"] / 2.0), 2)
    row["round_swing_rating"] = 1 + row["round_swing"] / 100 * 3.0
    row["rating"] = round(_rating_proxy(row), 3)
    row["rating3_proxy"] = row["rating"]
    row["impact_rating"] = round(max(0.0, 1 + safe_div(row["opening_duel_diff"], rounds) * 2.2 + safe_div(row["multi_kill_rounds"], rounds) * 1.6 + safe_div(row["trade_kills"], rounds) * 0.9), 3)

    row["firepower"] = round(clamp(
        0.38 * score(row["kpr"], 0.68, 0.95)
        + 0.30 * score(row["adr"], 75, 100)
        + 0.20 * score(row["multi_kill_rate"], 12, 25)
        + 0.12 * score(row["rounds_with_kill_percentage"], 43, 58)
    ))
    row["entrying"] = round(clamp(
        0.35 * score(row["traded_deaths_per_round"], 0.08, 0.18)
        + 0.30 * score(row["traded_deaths_percentage"], 15, 28)
        + 0.20 * score(row["saved_by_teammate_per_round"], 0.08, 0.18)
        + 0.15 * score(row["opening_deaths_traded_percentage"], 15, 35)
    ))
    row["trading"] = round(clamp(
        0.38 * score(row["trade_kills_per_round"], 0.10, 0.22)
        + 0.30 * score(row["trade_kills_percentage"], 12, 25)
        + 0.17 * score(row["saved_teammate_per_round"], 0.10, 0.22)
        + 0.15 * score(row["assisted_kills_percentage"], 12, 28)
    ))
    row["opening"] = round(clamp(
        0.35 * score(row["opening_kills_per_round"], 0.09, 0.18)
        + 0.25 * score(row["opening_attempts"], 18, 32)
        + 0.25 * score(row["opening_success"], 48, 62)
        + 0.15 * score(row["opening_deaths_per_round"], 0.13, 0.07, reverse=True)
    ))
    row["clutching"] = round(clamp(
        0.45 * score(row["clutch_points_per_round"], 0.01, 0.05)
        + 0.25 * score(row["last_alive_percentage"], 6, 14)
        + 0.30 * score(row["time_alive_per_round_seconds"], 60, 80)
    ))
    row["sniping"] = round(clamp(
        0.38 * score(row["sniper_kills_per_round"], 0.03, 0.28)
        + 0.24 * score(row["sniper_kills_percentage"], 3, 28)
        + 0.18 * score(row["rounds_with_sniper_kills_percentage"], 2, 18)
        + 0.10 * score(row["sniper_multi_kill_rounds_rate"], 0.002, 0.04)
        + 0.10 * score(row["sniper_opening_kills_per_round"], 0.002, 0.055)
    ))
    row["utility"] = round(clamp(
        0.45 * score(row["utility_damage_per_round"], 3.5, 8.5)
        + 0.20 * score(row["utility_kills_per_100_rounds"], 0.3, 1.2)
        + 0.20 * score(row["flash_assists_per_round"], 0.015, 0.08)
        + 0.10 * score(row["flashes_thrown_per_round"], 0.35, 0.8)
        + 0.05 * score(row["time_opponent_flashed_per_round"], 1.5, 3.5)
    ))
    return row


def _rating_proxy(row: dict[str, Any]) -> float:
    rounds = row.get("rounds", 0)
    if not rounds:
        return 0.0
    kpr = safe_div(row.get("kills", 0), rounds)
    dpr = safe_div(row.get("deaths", 0), rounds)
    adr = safe_div(row.get("damage", 0), rounds)
    kast = safe_div(row.get("kast_rounds", 0), rounds)
    multi = safe_div(row.get("multi_kill_rounds", 0), rounds)
    swing = (
        0.55 * safe_div(row.get("opening_kills", 0) - row.get("opening_deaths", 0), rounds)
        + 0.25 * safe_div(row.get("clutch_wins", 0), rounds)
        + 0.20 * safe_div(row.get("trade_kills", 0), rounds)
    )
    return max(
        0.0,
        0.18 * safe_div(kpr, 0.68)
        + 0.18 * safe_div(adr, 75)
        + 0.16 * safe_div(1 - dpr, 0.34)
        + 0.16 * safe_div(kast, 0.73)
        + 0.16 * safe_div(multi, 0.12)
        + 0.16 * (1 + swing * 3.0),
    )


def _with_sides(row: dict[str, Any]) -> dict[str, Any]:
    both = _compute_from_counts({k: v for k, v in row.items() if k != "side_stats"})
    sides = {"Both": {k: v for k, v in both.items() if k != "side_stats"}}
    for side in ("CT", "T"):
        side_row = {
            key: row.get(key)
            for key in ("player", "match_id", "date", "quarter", "map_name", "roster_type", "match_result", "roster_status")
            if key in row
        }
        side_row.update(row["side_stats"].get(side, empty_counts()))
        side_row["matches"] = row["matches"]
        sides[side] = _compute_from_counts(side_row)
    both["sides"] = sides
    return both


def _without_detail_lists(row: dict[str, Any]) -> dict[str, Any]:
    clean = dict(row)
    for field in DETAIL_LIST_FIELDS:
        clean.pop(field, None)
    if isinstance(clean.get("sides"), dict):
        clean["sides"] = {
            side: _without_detail_lists(side_row)
            for side, side_row in clean["sides"].items()
        }
    return clean


def add_stats(row: dict[str, Any], stats: PlayerMatchStats) -> None:
    _add_counts(row, stats)


def build_summary(match_rows: list[tuple[ReplayRecord, str, str, PlayerMatchStats]]) -> dict[str, Any]:
    by_player: dict[str, dict[str, Any]] = {}
    by_player_quarter: dict[tuple[str, str], dict[str, Any]] = {}
    by_player_map: dict[tuple[str, str], dict[str, Any]] = {}
    by_player_match: list[dict[str, Any]] = []
    by_match: dict[str, dict[str, Any]] = {}

    for replay, canonical_player, roster_status, stats in match_rows:
        player_row = by_player.setdefault(canonical_player, empty_aggregate({"player": canonical_player}))
        add_stats(player_row, stats)

        quarter_row = by_player_quarter.setdefault(
            (canonical_player, replay.quarter),
            empty_aggregate({"player": canonical_player, "quarter": replay.quarter}),
        )
        add_stats(quarter_row, stats)

        map_row = by_player_map.setdefault(
            (canonical_player, replay.map_name),
            empty_aggregate({"player": canonical_player, "map_name": replay.map_name}),
        )
        add_stats(map_row, stats)

        per_match = empty_aggregate({
            "player": canonical_player,
            "steam64": stats.steam64,
            "match_id": replay.match_id,
            "date": replay.match_date.isoformat(),
            "quarter": replay.quarter,
            "map_name": replay.map_name,
            "roster_type": replay.roster_type,
            "match_result": replay.match_result,
            "roster_status": roster_status,
        })
        add_stats(per_match, stats)
        by_player_match.append(_with_sides(per_match))

        team_row = by_match.setdefault(
            replay.match_id,
            empty_aggregate({
                "match_id": replay.match_id,
                "file_url": replay.file_url,
                "date": replay.match_date.isoformat(),
                "quarter": replay.quarter,
                "map_name": replay.map_name,
                "roster_type": replay.roster_type,
                "match_result": replay.match_result,
                "our_score": str(replay.our_score),
                "opponent_score": str(replay.opponent_score),
            }),
        )
        add_stats(team_row, stats)

    players = [_without_detail_lists(_with_sides(row)) for row in by_player.values()]
    quarters = [_without_detail_lists(_with_sides(row)) for row in by_player_quarter.values()]
    maps = [_without_detail_lists(_with_sides(row)) for row in by_player_map.values()]
    for row in by_match.values():
        row["rounds"] = int(row.get("our_score") or 0) + int(row.get("opponent_score") or 0)
        row["rounds_won"] = int(row.get("our_score") or 0)
    team_matches = [_with_sides(row) for row in by_match.values()]
    team = build_team_summary(team_matches)

    return {
        "players": sorted(players, key=lambda row: row["player"]),
        "player_quarters": sorted(quarters, key=lambda row: (row["player"], row["quarter"])),
        "player_maps": sorted(maps, key=lambda row: (row["player"], row["map_name"])),
        "player_matches": sorted((_without_detail_lists(row) for row in by_player_match), key=lambda row: (row["date"], row["player"])),
        "team": team,
        "metric_notes": {
            "rating": "Transparent Rating 3.0 proxy using HLTV-public sub-rating categories. It is not HLTV's private formula.",
            "side_stats": "Both/CT/T are derived from each player's side at round freeze end.",
            "trade": "Trade means a teammate killed the player's killer within five seconds in the same formal round.",
            "unsupported": "Exact clutch states, 1v1 win rate, and save intent still require deeper round-state extraction; current values are conservative proxies where marked.",
        },
    }


def build_team_summary(team_matches: list[dict[str, Any]]) -> dict[str, Any]:
    total = empty_aggregate({"scope": "team"})
    by_map: dict[str, dict[str, Any]] = {}
    for match in team_matches:
        total["matches"] += 1
        for field in COUNT_FIELDS:
            total[field] += match.get(field, 0) or 0
        total.setdefault("advantage_failures", []).extend(match.get("advantage_failures", []) or [])
        total.setdefault("clutch_rounds", []).extend(match.get("clutch_rounds", []) or [])
        total.setdefault("clutch_failures", []).extend(match.get("clutch_failures", []) or [])
        result = _result_key(match.get("match_result", ""))
        total[result] = total.get(result, 0) + 1

        map_name = match.get("map_name", "")
        map_row = by_map.setdefault(map_name, empty_aggregate({"map_name": map_name}))
        map_row["matches"] += 1
        for field in COUNT_FIELDS:
            map_row[field] += match.get(field, 0) or 0
        map_row.setdefault("advantage_failures", []).extend(match.get("advantage_failures", []) or [])
        map_row.setdefault("clutch_rounds", []).extend(match.get("clutch_rounds", []) or [])
        map_row.setdefault("clutch_failures", []).extend(match.get("clutch_failures", []) or [])
        map_row[result] = map_row.get(result, 0) + 1

    overview = _without_detail_lists(_with_sides(total))
    overview["maps_played"] = overview["matches"]
    overview["wins"] = total.get("win", 0)
    overview["draws"] = total.get("draw", 0)
    overview["losses"] = total.get("loss", 0)
    overview["record"] = f"{overview['wins']} / {overview['draws']} / {overview['losses']}"
    overview["win_rate"] = round(100 * safe_div(overview["wins"], overview["matches"]), 1)
    overview["round_win_rate"] = round(100 * safe_div(overview["rounds_won"], overview["rounds"]), 1)
    overview["five_v_four_win_rate"] = round(100 * safe_div(overview["opening_kill_round_wins"], overview["opening_kills"]), 1)
    overview["four_v_five_win_rate"] = round(100 * safe_div(overview["opening_death_round_wins"], overview["opening_deaths"]), 1)
    overview["maps_lost"] = overview["losses"]
    overview["map_pool_count"] = len(by_map)

    map_rows = []
    for row in by_map.values():
        computed = _with_sides(row)
        computed["pick_rate"] = round(100 * safe_div(computed["matches"], overview["matches"]), 1)
        computed["wins"] = row.get("win", 0)
        computed["draws"] = row.get("draw", 0)
        computed["losses"] = row.get("loss", 0)
        computed["record"] = f"{computed['wins']} / {computed['draws']} / {computed['losses']}"
        computed["win_rate"] = round(100 * safe_div(computed["wins"], computed["matches"]), 1)
        computed["round_win_rate"] = round(100 * safe_div(computed["rounds_won"], computed["rounds"]), 1)
        computed["five_v_four_win_rate"] = round(100 * safe_div(computed["opening_kill_round_wins"], computed["opening_kills"]), 1)
        computed["four_v_five_win_rate"] = round(100 * safe_div(computed["opening_death_round_wins"], computed["opening_deaths"]), 1)
        map_rows.append(_without_detail_lists(computed))

    return {
        "overview": overview,
        "maps": sorted(map_rows, key=lambda row: (-row["matches"], row["map_name"])),
        "matches": sorted(team_matches, key=lambda row: row["date"]),
    }


def _result_key(result: str) -> str:
    value = result.strip().lower()
    if value in {"win", "won", "w"}:
        return "win"
    if value in {"draw", "tie", "tied"}:
        return "draw"
    if value in {"loss", "lose", "lost", "l"}:
        return "loss"
    return value or "unknown"
