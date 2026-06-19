from __future__ import annotations

from collections import defaultdict
import math
from pathlib import Path
from typing import Any

from .models import PlayerDiscovery, PlayerMatchStats, ReplayRecord


class DemoParseError(RuntimeError):
    pass


def _load_demoparser() -> Any:
    try:
        from demoparser2 import DemoParser
    except ImportError as exc:
        raise DemoParseError(
            "demoparser2 is not installed. Install dependencies with `pip install -e .`."
        ) from exc
    return DemoParser


def _records(df_or_records: Any) -> list[dict[str, Any]]:
    if df_or_records is None:
        return []
    if hasattr(df_or_records, "to_dict"):
        return df_or_records.to_dict("records")
    if isinstance(df_or_records, list):
        return [dict(row) for row in df_or_records]
    return []


def _first_present(row: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def _steam(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return str(int(value)) if value.is_integer() else format(value, ".0f")
    text = str(value).strip()
    if "e+" in text.lower() or "e-" in text.lower():
        try:
            return format(float(text), ".0f")
        except ValueError:
            pass
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _round_no(row: dict[str, Any]) -> int:
    return int(float(_first_present(row, ["total_rounds_played"]) or 0))


def _is_formal_round_event(row: dict[str, Any], rounds: int) -> bool:
    if bool(_first_present(row, ["is_warmup_period"])):
        return False
    round_no = _round_no(row)
    return 0 <= round_no < rounds


def _damage_value(row: dict[str, Any]) -> int:
    raw = int(float(_first_present(row, ["dmg_health"]) or 0))
    return max(0, min(raw, 100))


def _float_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def _int_value(value: Any) -> int:
    parsed = _float_value(value)
    return int(parsed) if parsed is not None else 0


def _side(team_num: Any) -> str:
    try:
        value = int(float(team_num))
    except (TypeError, ValueError):
        return ""
    if value == 2:
        return "T"
    if value == 3:
        return "CT"
    return ""


def _opposite_side(side: str) -> str:
    if side == "CT":
        return "T"
    if side == "T":
        return "CT"
    return ""


def _empty_side_stats() -> dict[str, int]:
    return {
        "rounds": 0,
        "rounds_won": 0,
        "kills_in_round_wins": 0,
        "damage_in_round_wins": 0,
        "kills": 0,
        "deaths": 0,
        "assists": 0,
        "damage": 0,
        "opening_kills": 0,
        "opening_kill_round_wins": 0,
        "opening_deaths": 0,
        "opening_death_round_wins": 0,
        "trade_kills": 0,
        "traded_deaths": 0,
        "opening_deaths_traded": 0,
        "flash_assists": 0,
        "flashes_thrown": 0,
        "opponent_flashed_count": 0,
        "opponent_flashed_time": 0,
        "teammate_flashed_count": 0,
        "teammate_flashed_time": 0,
        "utility_damage": 0,
        "he_damage": 0,
        "fire_damage": 0,
        "utility_kills": 0,
        "multi_kill_rounds": 0,
        "clutch_attempts": 0,
        "clutch_wins": 0,
        "clutch_losses": 0,
        "clutch_broad_attempts": 0,
        "clutch_broad_wins": 0,
        "clutch_broad_losses": 0,
        "kast_rounds": 0,
        "headshot_kills": 0,
        "survived_rounds": 0,
        "rounds_with_kill": 0,
        "support_rounds": 0,
        "assisted_kills": 0,
        "sniper_kills": 0,
        "sniper_multi_kill_rounds": 0,
        "sniper_opening_kills": 0,
        "pistol_rounds": 0,
        "pistol_kills": 0,
        "pistol_deaths": 0,
        "pistol_assists": 0,
        "pistol_damage": 0,
        "pistol_kast_rounds": 0,
    }


def _add(item: PlayerMatchStats, side: str, field: str, amount: float = 1) -> None:
    setattr(item, field, getattr(item, field) + amount)
    if side:
        side_row = item.side_stats.setdefault(side, _empty_side_stats())
        side_row[field] = side_row.get(field, 0) + amount


def _weapon(row: dict[str, Any]) -> str:
    return str(_first_present(row, ["weapon"]) or "").lower()


UTILITY_WEAPONS = {"hegrenade", "inferno", "molotov", "incgrenade"}
SNIPER_WEAPONS = {"awp", "ssg08", "scar20", "g3sg1"}
RIFLE_WEAPONS = {"AK-47", "M4A1-S", "M4A4", "Galil AR", "FAMAS", "SG 553", "AUG"}
PRIMARY_BUY_WEAPONS = RIFLE_WEAPONS | {"AWP"}
GRENADE_LABELS = {
    "Smoke Grenade": "smoke",
    "Flashbang": "flash",
    "HE Grenade": "he",
    "Molotov": "fire",
    "Incendiary Grenade": "fire",
    "Decoy Grenade": "decoy",
}
ACCOUNT_COL = "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iAccount"
START_ACCOUNT_COL = "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iStartAccount"
CASH_SPENT_COL = "CCSPlayerController.CCSPlayerController_InGameMoneyServices.m_iCashSpentThisRound"
EQUIP_VALUE_COL = "CCSPlayerPawn.m_unFreezetimeEndEquipmentValue"
ARMOR_COL = "CCSPlayerPawn.m_ArmorValue"
HELMET_COL = "CCSPlayerPawn.CCSPlayer_ItemServices.m_bHasHelmet"
DEFUSER_COL = "CCSPlayerPawn.CCSPlayer_ItemServices.m_bHasDefuser"


def _inventory(row: dict[str, Any]) -> list[str]:
    value = row.get("inventory") or []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _grenade_counts(inventory: list[str]) -> dict[str, int]:
    counts = {key: 0 for key in ("smoke", "flash", "he", "fire", "decoy")}
    for item in inventory:
        key = GRENADE_LABELS.get(item)
        if key:
            counts[key] += 1
    return counts


def _team_buy_snapshot(players: list[dict[str, Any]], side: str, round_no: int) -> dict[str, Any]:
    count = len(players)
    if not count:
        return {
            "type": "No Buy Data",
            "players": 0,
            "utility": {key: 0 for key in ("smoke", "flash", "he", "fire", "decoy")},
        }
    utility = {key: 0 for key in ("smoke", "flash", "he", "fire", "decoy")}
    start_money = []
    spent = []
    remaining = []
    equipment = []
    primary_count = 0
    armor_count = 0
    helmet_count = 0
    kit_count = 0
    buyers = 0
    for player in players:
        inventory = _inventory(player)
        for key, value in _grenade_counts(inventory).items():
            utility[key] += value
        if PRIMARY_BUY_WEAPONS.intersection(inventory):
            primary_count += 1
        armor = _int_value(player.get(ARMOR_COL))
        if armor > 0:
            armor_count += 1
        if bool(player.get(HELMET_COL)):
            helmet_count += 1
        if bool(player.get(DEFUSER_COL)):
            kit_count += 1
        player_start = _int_value(player.get(START_ACCOUNT_COL))
        player_spent = _int_value(player.get(CASH_SPENT_COL))
        player_remaining = _int_value(player.get(ACCOUNT_COL))
        start_money.append(player_start)
        spent.append(player_spent)
        remaining.append(player_remaining)
        equipment.append(_int_value(player.get(EQUIP_VALUE_COL)))
        if player_spent >= 300:
            buyers += 1

    avg_start = sum(start_money) / count
    avg_spent = sum(spent) / count
    avg_remaining = sum(remaining) / count
    avg_equipment = sum(equipment) / count
    total_utility = sum(utility.values())
    avg_utility = total_utility / count
    all_armor = armor_count == count
    helmet_ready = side == "CT" or helmet_count == count
    type_name = "Half Buy"
    if round_no in {0, 12}:
        type_name = "Pistol"
    elif primary_count >= min(4, count) and all_armor and helmet_ready and avg_utility >= 3.5:
        type_name = "Full Buy"
    elif avg_start > 4500 and primary_count >= min(4, count) and armor_count >= max(1, count - 1):
        type_name = "Light Full Buy"
    elif avg_start <= 2500 and avg_spent <= 2200 and primary_count <= 1 and avg_equipment <= 2600:
        type_name = "Eco"
    elif avg_start <= 2500 and (primary_count >= 2 or avg_equipment >= 2800):
        type_name = "Saved Buy"
    elif avg_start <= 3500 and buyers >= min(4, count) and avg_remaining <= 900 and avg_spent >= 1000:
        type_name = "Force Buy"
    elif 3500 < avg_start <= 4500 and primary_count >= min(4, count) and armor_count >= max(1, count - 1):
        type_name = "4K Buy"

    return {
        "type": type_name,
        "players": count,
        "avg_start_money": round(avg_start),
        "avg_spent": round(avg_spent),
        "avg_remaining": round(avg_remaining),
        "avg_equipment": round(avg_equipment),
        "avg_utility": round(avg_utility, 1),
        "primary_count": primary_count,
        "armor_count": armor_count,
        "helmet_count": helmet_count,
        "kit_count": kit_count,
        "buyers": buyers,
        "utility": utility,
    }


def discover_players(demo_path: Path, replay: ReplayRecord) -> dict[str, PlayerDiscovery]:
    DemoParser = _load_demoparser()
    parser = DemoParser(str(demo_path))
    rows: list[dict[str, Any]] = []

    for fields in (
        ["player_steamid", "player_name", "team_name", "team_num"],
        ["steamid", "name", "team_name", "team_num"],
    ):
        try:
            parsed = parser.parse_ticks(fields)
            rows = _records(parsed)
            if rows:
                break
        except Exception:
            continue

    if not rows:
        raise DemoParseError(f"No player identity rows parsed from {demo_path}")

    discovered: dict[str, PlayerDiscovery] = {}
    for row in rows:
        steam64 = _steam(_first_present(row, ["steamid", "player_steamid", "user_steamid"]))
        if not steam64 or steam64 == "0":
            continue
        name = str(_first_present(row, ["name", "player_name", "user_name"]) or "").strip()
        team_name = _first_present(row, ["team_name", "user_team_name"])
        item = discovered.setdefault(steam64, PlayerDiscovery(steam64=steam64))
        item.add(name, replay, str(team_name) if team_name is not None else None)
    return discovered


def parse_match_stats(demo_path: Path, replay: ReplayRecord) -> dict[str, PlayerMatchStats]:
    DemoParser = _load_demoparser()
    parser = DemoParser(str(demo_path))
    stats: dict[str, PlayerMatchStats] = {}
    rounds = max(replay.our_score + replay.opponent_score, 1)
    pistol_round_indexes = {0}
    if rounds > 12:
        pistol_round_indexes.add(12)

    def get_player(steam64: str, name: str = "") -> PlayerMatchStats:
        item = stats.setdefault(steam64, PlayerMatchStats(steam64=steam64, name=name))
        if name and not item.name:
            item.name = name
        return item

    round_winners: dict[int, str] = {}
    try:
        round_end_rows = _records(parser.parse_event(
            "round_end",
            other=["is_warmup_period", "total_rounds_played", "winner"],
        ))
    except Exception:
        round_end_rows = []
    for row in round_end_rows:
        if bool(_first_present(row, ["is_warmup_period"])):
            continue
        completed = _round_no(row)
        round_no = completed - 1
        if 0 <= round_no < rounds:
            winner = str(_first_present(row, ["winner"]) or "").upper()
            if winner in {"CT", "T"}:
                round_winners[round_no] = winner

    player_round_side: dict[str, dict[int, str]] = defaultdict(dict)
    try:
        freeze_rows = _records(parser.parse_event(
            "round_freeze_end",
            other=["is_warmup_period", "total_rounds_played", "tick"],
        ))
        freeze_ticks = [
            int(row["tick"])
            for row in freeze_rows
            if _is_formal_round_event(row, rounds) and row.get("tick") is not None
        ]
        tick_rows = _records(parser.parse_ticks(
            [
                "player_steamid",
                "player_name",
                "team_num",
                "total_rounds_played",
                "inventory",
                ACCOUNT_COL,
                START_ACCOUNT_COL,
                CASH_SPENT_COL,
                EQUIP_VALUE_COL,
                ARMOR_COL,
                HELMET_COL,
                DEFUSER_COL,
            ],
            ticks=freeze_ticks,
        ))
    except Exception:
        tick_rows = []
    for row in tick_rows:
        round_no = _round_no(row)
        if not 0 <= round_no < rounds:
            continue
        steam64 = _steam(_first_present(row, ["steamid", "player_steamid"]))
        side = _side(_first_present(row, ["team_num"]))
        if not steam64 or steam64 == "0" or not side:
            continue
        item = get_player(steam64, str(_first_present(row, ["name", "player_name"]) or ""))
        if round_no not in player_round_side[steam64]:
            player_round_side[steam64][round_no] = side
            _add(item, side, "rounds")
            if round_winners.get(round_no) == side:
                _add(item, side, "rounds_won")
            if round_no in pistol_round_indexes:
                _add(item, side, "pistol_rounds")

    missing_round_side: dict[int, dict[str, str]] = defaultdict(dict)
    for row in tick_rows:
        round_no = _round_no(row)
        if not 0 <= round_no < rounds:
            continue
        steam64 = _steam(_first_present(row, ["steamid", "player_steamid"]))
        side = _side(_first_present(row, ["team_num"]))
        if steam64 and steam64 != "0" and not side:
            missing_round_side[round_no][steam64] = str(_first_present(row, ["name", "player_name"]) or "")

    round_freeze_players: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {"CT": [], "T": []})
    for row in tick_rows:
        round_no = _round_no(row)
        if not 0 <= round_no < rounds:
            continue
        steam64 = _steam(_first_present(row, ["steamid", "player_steamid"]))
        side = _side(_first_present(row, ["team_num"])) or player_round_side.get(steam64, {}).get(round_no, "")
        if steam64 and steam64 != "0" and side in {"CT", "T"}:
            round_freeze_players[round_no][side].append(row)

    def note_participation(steam64: str, name: str, round_no: int, side: str) -> None:
        if not steam64 or steam64 == "0" or not side or not 0 <= round_no < rounds:
            return
        item = get_player(steam64, name)
        if round_no in player_round_side[steam64]:
            return
        player_round_side[steam64][round_no] = side
        _add(item, side, "rounds")
        if round_winners.get(round_no) == side:
            _add(item, side, "rounds_won")
        if round_no in pistol_round_indexes:
            _add(item, side, "pistol_rounds")

    def infer_missing_round_sides() -> None:
        try:
            side_death_rows = _records(parser.parse_event(
                "player_death",
                player=["player_steamid", "player_name"],
                other=[
                    "attacker_steamid",
                    "attacker_name",
                    "is_warmup_period",
                    "total_rounds_played",
                ],
            ))
        except Exception:
            side_death_rows = []
        try:
            side_hurt_rows = _records(parser.parse_event(
                "player_hurt",
                player=["player_steamid", "player_name"],
                other=[
                    "attacker_steamid",
                    "attacker_name",
                    "is_warmup_period",
                    "total_rounds_played",
                ],
            ))
        except Exception:
            side_hurt_rows = []

        relations: list[tuple[int, str, str, str, str]] = []
        for row in side_death_rows + side_hurt_rows:
            if not _is_formal_round_event(row, rounds):
                continue
            round_no = _round_no(row)
            attacker = _steam(_first_present(row, ["attacker_steamid"]))
            victim = _steam(_first_present(row, ["user_steamid", "user_player_steamid", "player_steamid"]))
            if not attacker or not victim or attacker == "0" or victim == "0" or attacker == victim:
                continue
            relations.append((
                round_no,
                attacker,
                str(_first_present(row, ["attacker_name"]) or ""),
                victim,
                str(_first_present(row, ["user_name", "user_player_name", "player_name"]) or ""),
            ))

        changed = True
        while changed:
            changed = False
            for round_no, attacker, attacker_name, victim, victim_name in relations:
                attacker_side = player_round_side.get(attacker, {}).get(round_no, "")
                victim_side = player_round_side.get(victim, {}).get(round_no, "")
                if attacker_side and not victim_side and victim in missing_round_side.get(round_no, {}):
                    inferred = _opposite_side(attacker_side)
                    note_participation(victim, victim_name or missing_round_side[round_no][victim], round_no, inferred)
                    changed = True
                elif victim_side and not attacker_side and attacker in missing_round_side.get(round_no, {}):
                    inferred = _opposite_side(victim_side)
                    note_participation(attacker, attacker_name or missing_round_side[round_no][attacker], round_no, inferred)
                    changed = True

        for round_no, players in missing_round_side.items():
            unresolved = [
                (steam64, name)
                for steam64, name in players.items()
                if not player_round_side.get(steam64, {}).get(round_no)
            ]
            if len(unresolved) != 1:
                continue
            known_sides = [sides.get(round_no) for sides in player_round_side.values()]
            ct_count = known_sides.count("CT")
            t_count = known_sides.count("T")
            inferred = ""
            if ct_count == 5 and t_count == 4:
                inferred = "T"
            elif t_count == 5 and ct_count == 4:
                inferred = "CT"
            if inferred:
                steam64, name = unresolved[0]
                note_participation(steam64, name, round_no, inferred)

    infer_missing_round_sides()

    try:
        flash_rows = _records(parser.parse_event(
            "flashbang_detonate",
            player=["player_steamid", "player_name"],
            other=["user_steamid", "is_warmup_period", "total_rounds_played"],
        ))
    except Exception:
        flash_rows = []
    for row in flash_rows:
        if not _is_formal_round_event(row, rounds):
            continue
        round_no = _round_no(row)
        thrower = _steam(_first_present(row, ["user_steamid", "user_player_steamid", "player_steamid"]))
        if not thrower or thrower == "0":
            continue
        side = player_round_side.get(thrower, {}).get(round_no, "")
        _add(get_player(thrower, str(_first_present(row, ["user_name", "user_player_name", "player_name"]) or "")), side, "flashes_thrown")

    try:
        blind_rows = _records(parser.parse_event(
            "player_blind",
            player=["player_steamid", "player_name"],
            other=[
                "attacker_steamid",
                "attacker_name",
                "user_steamid",
                "blind_duration",
                "is_warmup_period",
                "total_rounds_played",
            ],
        ))
    except Exception:
        blind_rows = []
    for row in blind_rows:
        if not _is_formal_round_event(row, rounds):
            continue
        round_no = _round_no(row)
        attacker = _steam(_first_present(row, ["attacker_steamid"]))
        victim = _steam(_first_present(row, ["user_steamid", "user_player_steamid", "player_steamid"]))
        if not attacker or attacker == "0" or not victim or victim == "0" or attacker == victim:
            continue
        attacker_side = player_round_side.get(attacker, {}).get(round_no, "")
        victim_side = player_round_side.get(victim, {}).get(round_no, "")
        if not attacker_side:
            continue
        duration = _float_value(_first_present(row, ["blind_duration"])) or 0.0
        item = get_player(attacker, str(_first_present(row, ["attacker_name"]) or ""))
        if attacker_side == victim_side:
            _add(item, attacker_side, "teammate_flashed_count")
            _add(item, attacker_side, "teammate_flashed_time", duration)
        else:
            _add(item, attacker_side, "opponent_flashed_count")
            _add(item, attacker_side, "opponent_flashed_time", duration)

    try:
        hurt_rows = _records(parser.parse_event(
            "player_hurt",
            player=["player_steamid", "player_name"],
            other=[
                "attacker_steamid",
                "attacker_name",
                "attacker_team_num",
                "dmg_health",
                "is_warmup_period",
                "total_rounds_played",
                "weapon",
            ],
        ))
    except Exception:
        hurt_rows = []
    for row in hurt_rows:
        if not _is_formal_round_event(row, rounds):
            continue
        attacker = _steam(_first_present(row, ["attacker_steamid"]))
        if not attacker or attacker == "0":
            continue
        name = str(_first_present(row, ["attacker_name"]) or "")
        item = get_player(attacker, name)
        round_no = _round_no(row)
        side = _side(_first_present(row, ["attacker_team_num"])) or player_round_side.get(attacker, {}).get(round_no, "")
        note_participation(attacker, name, round_no, side)
        damage = _damage_value(row)
        _add(item, side, "damage", damage)
        if side and round_winners.get(round_no) == side:
            _add(item, side, "damage_in_round_wins", damage)
        if round_no in pistol_round_indexes:
            _add(item, side, "pistol_damage", damage)
        weapon = _weapon(row)
        if weapon in UTILITY_WEAPONS:
            _add(item, side, "utility_damage", damage)
        if weapon == "hegrenade":
            _add(item, side, "he_damage", damage)
        elif weapon in {"inferno", "molotov", "incgrenade"}:
            _add(item, side, "fire_damage", damage)

    try:
        death_rows = _records(parser.parse_event(
            "player_death",
            player=["player_steamid", "player_name"],
            other=[
                "attacker_steamid",
                "attacker_name",
                "attacker_team_num",
                "assister_steamid",
                "assister_name",
                "headshot",
                "assistedflash",
                "is_warmup_period",
                "total_rounds_played",
                "tick",
                "game_time",
                "user_team_num",
                "weapon",
            ],
        ))
    except Exception:
        death_rows = []

    kills_by_round: dict[tuple[str, str, int], int] = defaultdict(int)
    sniper_kills_by_round: dict[tuple[str, str, int], int] = defaultdict(int)
    kill_rounds: dict[tuple[str, str], set[int]] = defaultdict(set)
    assist_rounds: dict[tuple[str, str], set[int]] = defaultdict(set)
    death_rounds: dict[tuple[str, str], set[int]] = defaultdict(set)
    trade_rounds: dict[tuple[str, str], set[int]] = defaultdict(set)
    support_rounds: dict[tuple[str, str], set[int]] = defaultdict(set)
    first_death_seen: set[int] = set()
    opening_deaths: dict[tuple[str, int], str] = {}
    formal_deaths: list[dict[str, Any]] = []
    for row in death_rows:
        if not _is_formal_round_event(row, rounds):
            continue
        victim = _steam(_first_present(row, ["user_steamid", "user_player_steamid", "player_steamid"]))
        victim_name = str(_first_present(row, ["user_name", "user_player_name", "player_name"]) or "")
        attacker = _steam(_first_present(row, ["attacker_steamid"]))
        attacker_name = str(_first_present(row, ["attacker_name"]) or "")
        assister = _steam(_first_present(row, ["assister_steamid"]))
        round_no = _round_no(row)
        is_headshot = bool(_first_present(row, ["headshot"]))
        assisted_flash = bool(_first_present(row, ["assistedflash"]))
        victim_team = _first_present(row, ["user_team_num"])
        attacker_team = _first_present(row, ["attacker_team_num"])
        game_time = _float_value(_first_present(row, ["game_time"]))
        weapon = _weapon(row)
        victim_side = _side(victim_team) or player_round_side.get(victim, {}).get(round_no, "")
        attacker_side = _side(attacker_team) or player_round_side.get(attacker, {}).get(round_no, "")

        if victim and victim != "0":
            note_participation(victim, victim_name, round_no, victim_side)
            death_rounds[(victim, victim_side)].add(round_no)
            victim_item = get_player(victim, victim_name)
            _add(victim_item, victim_side, "deaths")
            if round_no in pistol_round_indexes:
                _add(victim_item, victim_side, "pistol_deaths")
        if attacker and attacker != "0" and attacker != victim:
            note_participation(attacker, attacker_name, round_no, attacker_side)
            killer = get_player(attacker, attacker_name)
            _add(killer, attacker_side, "kills")
            if attacker_side and round_winners.get(round_no) == attacker_side:
                _add(killer, attacker_side, "kills_in_round_wins")
            if is_headshot:
                _add(killer, attacker_side, "headshot_kills")
            if weapon in UTILITY_WEAPONS:
                _add(killer, attacker_side, "utility_kills")
            if weapon in SNIPER_WEAPONS:
                _add(killer, attacker_side, "sniper_kills")
                sniper_kills_by_round[(attacker, attacker_side, round_no)] += 1
            if round_no in pistol_round_indexes:
                _add(killer, attacker_side, "pistol_kills")
            kills_by_round[(attacker, attacker_side, round_no)] += 1
            kill_rounds[(attacker, attacker_side)].add(round_no)
        if assister and assister != "0" and assister != attacker:
            assister_side = player_round_side.get(assister, {}).get(round_no, "")
            assist_rounds[(assister, assister_side)].add(round_no)
            support_rounds[(assister, assister_side)].add(round_no)
            assister_item = get_player(assister)
            _add(assister_item, assister_side, "assists")
            if attacker and attacker != "0":
                _add(assister_item, assister_side, "assisted_kills")
            if assisted_flash:
                _add(assister_item, assister_side, "flash_assists")
            if round_no in pistol_round_indexes:
                _add(assister_item, assister_side, "pistol_assists")

        if round_no not in first_death_seen:
            first_death_seen.add(round_no)
            if attacker and attacker != "0" and attacker != victim:
                attacker_item = get_player(attacker, attacker_name)
                _add(attacker_item, attacker_side, "opening_kills")
                if attacker_side and round_winners.get(round_no) == attacker_side:
                    _add(attacker_item, attacker_side, "opening_kill_round_wins")
                if weapon in SNIPER_WEAPONS:
                    _add(attacker_item, attacker_side, "sniper_opening_kills")
            if victim and victim != "0":
                _add(get_player(victim, victim_name), victim_side, "opening_deaths")
                if victim_side and round_winners.get(round_no) == victim_side:
                    _add(get_player(victim, victim_name), victim_side, "opening_death_round_wins")
                opening_deaths[(victim, round_no)] = victim_side

        if victim and victim != "0" and attacker and attacker != "0" and attacker != victim:
            formal_deaths.append({
                "round": round_no,
                "time": game_time,
                "victim": victim,
                "victim_side": victim_side,
                "attacker": attacker,
                "attacker_side": attacker_side,
            })

    deaths_by_round: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(formal_deaths, key=lambda item: (item["round"], item["time"] or 0.0)):
        deaths_by_round[row["round"]].append(row)

    trade_window_seconds = 5.0
    for round_no, rows in deaths_by_round.items():
        for death in rows:
            death_time = death["time"]
            if death_time is None:
                continue
            for later in rows:
                later_time = later["time"]
                if later_time is None or later_time <= death_time:
                    continue
                if later_time - death_time > trade_window_seconds:
                    break
                if later["victim"] != death["attacker"]:
                    continue
                if later["attacker"] == death["victim"]:
                    continue
                if later["attacker_side"] != death["victim_side"]:
                    continue
                trade_rounds[(death["victim"], death["victim_side"])].add(round_no)
                _add(get_player(death["victim"]), death["victim_side"], "traded_deaths")
                _add(get_player(later["attacker"]), later["attacker_side"], "trade_kills")
                if (death["victim"], round_no) in opening_deaths:
                    _add(get_player(death["victim"]), death["victim_side"], "opening_deaths_traded")
                break

    for round_no in range(rounds):
        side_alive = {
            "CT": {steam for steam, sides in player_round_side.items() if sides.get(round_no) == "CT"},
            "T": {steam for steam, sides in player_round_side.items() if sides.get(round_no) == "T"},
        }
        if not side_alive["CT"] or not side_alive["T"]:
            continue
        side_start_counts = {side: len(players) for side, players in side_alive.items()}
        best_advantage: dict[str, tuple[int, str, list[str]] | None] = {"CT": None, "T": None}
        narrow_candidates: dict[str, tuple[str, int] | None] = {"CT": None, "T": None}
        broad_candidates: dict[str, tuple[int, int, list[str], list[str]] | None] = {"CT": None, "T": None}
        last_death_by_side: dict[str, str] = {}

        for death in deaths_by_round.get(round_no, []):
            victim = death["victim"]
            victim_side = death["victim_side"]
            if victim_side in side_alive:
                side_alive[victim_side].discard(victim)
                last_death_by_side[victim_side] = victim

            for side, opponent in (("CT", "T"), ("T", "CT")):
                own_count = len(side_alive[side])
                opponent_count = len(side_alive[opponent])
                if own_count > opponent_count > 0:
                    diff = own_count - opponent_count
                    state = f"{own_count}v{opponent_count}"
                    current = best_advantage[side]
                    if current is None or diff > current[0] or (diff == current[0] and own_count > int(current[1].split("v", 1)[0])):
                        best_advantage[side] = (diff, state, sorted(side_alive[side]))
                if own_count == 1 and opponent_count > 0 and narrow_candidates[side] is None:
                    narrow_candidates[side] = (next(iter(side_alive[side])), opponent_count)
                if (
                    (
                        own_count == 1 and opponent_count > 0
                        or (own_count, opponent_count) in {(2, 4), (2, 5), (3, 5)}
                    )
                    and broad_candidates[side] is None
                ):
                    broad_candidates[side] = (own_count, opponent_count, sorted(side_alive[side]), sorted(side_alive[opponent]))

        winner = round_winners.get(round_no)
        if winner in {"CT", "T"}:
            loser = "T" if winner == "CT" else "CT"
            narrow = narrow_candidates.get(winner)
            if narrow is not None:
                steam64, opponent_count = narrow
                item = get_player(steam64)
                player_side = player_round_side.get(steam64, {}).get(round_no, winner)
                _add(item, player_side, "clutch_attempts")
                _add(item, player_side, "clutch_wins")
                loser_owner = last_death_by_side.get(loser)
                if loser_owner:
                    _add(get_player(loser_owner), loser, "clutch_losses")
                item.clutch_rounds.append({
                    "round": round_no + 1,
                    "side": winner,
                    "opponents": opponent_count,
                    "state": f"1v{opponent_count}",
                    "won": True,
                    "winner": winner,
                    "scope": "narrow",
                })

            broad = broad_candidates.get(winner)
            if broad is not None:
                own_count, opponent_count, alive_steam64s, opponent_alive_steam64s = broad
                owner = next(iter(side_alive[winner]), "")
                if owner:
                    item = get_player(owner)
                    player_side = player_round_side.get(owner, {}).get(round_no, winner)
                    _add(item, player_side, "clutch_broad_attempts")
                    _add(item, player_side, "clutch_broad_wins")
                    loser_owner = last_death_by_side.get(loser)
                    if loser_owner:
                        _add(get_player(loser_owner), loser, "clutch_broad_losses")
                        get_player(loser_owner).clutch_failures.append({
                            "round": round_no + 1,
                            "side": loser,
                            "state": f"{opponent_count}v{own_count}",
                            "winner": winner,
                            "alive_steam64s": opponent_alive_steam64s,
                        })
                    item.clutch_rounds.append({
                        "round": round_no + 1,
                        "side": winner,
                        "opponents": opponent_count,
                        "state": f"{own_count}v{opponent_count}",
                        "won": True,
                        "winner": winner,
                        "scope": "broad",
                        "alive_steam64s": alive_steam64s,
                    })

        if winner in {"CT", "T"}:
            losing_side = "T" if winner == "CT" else "CT"
            failure = best_advantage.get(losing_side)
            if failure is not None:
                losing_players = [
                    death["victim"]
                    for death in deaths_by_round.get(round_no, [])
                    if death["victim_side"] == losing_side
                ]
                owner = losing_players[-1] if losing_players else next(iter(side_alive[losing_side]), "")
                if owner:
                    get_player(owner).advantage_failures.append({
                        "round": round_no + 1,
                        "side": losing_side,
                        "state": failure[1],
                        "winner": winner,
                        "start_ct": side_start_counts["CT"],
                        "start_t": side_start_counts["T"],
                        "alive_steam64s": failure[2],
                    })

        for side in ("CT", "T"):
            if not side_start_counts.get(side):
                continue
            side_players = sorted(
                steam64
                for steam64, sides in player_round_side.items()
                if sides.get(round_no) == side
            )
            if not side_players:
                continue
            highlights = [
                {"steam64": steam64, "kills": kills}
                for (steam64, kill_side, kill_round), kills in kills_by_round.items()
                if kill_round == round_no and kill_side == side and kills >= 4
            ]
            detail = {
                "round": round_no + 1,
                "side": side,
                "winner": winner or "",
                "won": winner == side,
                "start_count": side_start_counts[side],
                "alive_count": len(side_alive[side]),
                "alive_steam64s": sorted(side_alive[side]),
                "buy": _team_buy_snapshot(round_freeze_players.get(round_no, {}).get(side, []), side, round_no),
                "opponent_buy": _team_buy_snapshot(
                    round_freeze_players.get(round_no, {}).get(_opposite_side(side), []),
                    _opposite_side(side),
                    round_no,
                ),
                "highlights": sorted(highlights, key=lambda item: (-int(item["kills"]), str(item["steam64"]))),
            }
            for steam64 in side_players:
                get_player(steam64).round_details.append(detail)

    for (steam64, side, round_index), kills in kills_by_round.items():
        if kills >= 2:
            _add(stats[steam64], side, "multi_kill_rounds")
        _add(stats[steam64], side, "rounds_with_kill")
    for (steam64, side, round_index), kills in sniper_kills_by_round.items():
        if kills >= 2:
            _add(stats[steam64], side, "sniper_multi_kill_rounds")
    for (steam64, side), rounds_set in support_rounds.items():
        for _ in rounds_set:
            _add(stats[steam64], side, "support_rounds")

    for item in stats.values():
        for side, side_row in item.side_stats.items():
            participated = {
                round_no
                for round_no, round_side in player_round_side.get(item.steam64, {}).items()
                if round_side == side
            }
            survived = participated - death_rounds[(item.steam64, side)]
            side_row["survived_rounds"] = len(survived)
            kast = kill_rounds[(item.steam64, side)] | assist_rounds[(item.steam64, side)] | survived | trade_rounds[(item.steam64, side)]
            side_row["kast_rounds"] = min(side_row.get("rounds", 0), len(kast))
            pistol_participated = participated & pistol_round_indexes
            if pistol_participated:
                pistol_kast = kast & pistol_participated
                side_row["pistol_kast_rounds"] = len(pistol_kast)
        for side_row in item.side_stats.values():
            for field, value in side_row.items():
                if field in {"survived_rounds", "kast_rounds", "pistol_kast_rounds"}:
                    setattr(item, field, getattr(item, field) + value)

    return stats
