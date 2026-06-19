from datetime import date

from cs2demo_analyse.analytics import build_summary, split_summary_payload
from cs2demo_analyse.models import PlayerMatchStats, ReplayRecord


def test_build_summary_by_player_and_quarter():
    replay = ReplayRecord(
        file_id="demo1",
        file_url="",
        match_date=date(2026, 6, 12),
        map_name="dust2",
        roster_type="full",
        match_result="win",
        our_score=13,
        opponent_score=9,
    )
    stats = PlayerMatchStats(steam64="765", name="A", kills=22, deaths=10, damage=2100, rounds=22, kast_rounds=18)

    summary = build_summary([(replay, "Add1t", "Starter", stats)])

    assert summary["players"][0]["player"] == "Add1t"
    assert summary["players"][0]["kills"] == 22
    assert summary["player_quarters"][0]["quarter"] == "2026-Q2"


def test_build_summary_team_overview_and_maps():
    replay = ReplayRecord(
        file_id="demo2",
        file_url="",
        match_date=date(2026, 6, 13),
        map_name="mirage",
        roster_type="full",
        match_result="loss",
        our_score=11,
        opponent_score=13,
    )
    stats = PlayerMatchStats(
        steam64="765",
        name="A",
        kills=18,
        deaths=20,
        damage=1700,
        rounds=24,
        rounds_won=11,
        opening_kills=4,
        opening_kill_round_wins=2,
        opening_deaths=5,
        opening_death_round_wins=1,
    )

    summary = build_summary([(replay, "Add1t", "Starter", stats)])
    overview = summary["team"]["overview"]
    map_row = summary["team"]["maps"][0]

    assert overview["maps_played"] == 1
    assert overview["record"] == "0 / 0 / 1"
    assert overview["rounds"] == 24
    assert overview["round_win_rate"] == 45.8
    assert overview["five_v_four_win_rate"] == 50.0
    assert overview["four_v_five_win_rate"] == 20.0
    assert map_row["map_name"] == "mirage"
    assert map_row["record"] == "0 / 0 / 1"


def test_split_summary_payload_moves_match_details_out_of_summary():
    replay = ReplayRecord(
        file_id="demo3",
        file_url="",
        match_date=date(2026, 6, 14),
        map_name="nuke",
        roster_type="full",
        match_result="win",
        our_score=13,
        opponent_score=7,
    )
    stats = PlayerMatchStats(
        steam64="765",
        name="A",
        kills=20,
        deaths=8,
        damage=1900,
        rounds=20,
        round_details=[{"round": 1, "side": "CT", "won": True}],
        clutch_failures=[{"round": 2, "side": "T", "state": "1v1"}],
        advantage_failures=[{"round": 3, "side": "CT", "state": "5v4"}],
    )

    summary = build_summary([(replay, "Add1t", "Starter", stats)])
    slim, player_summary, player_matches, details = split_summary_payload(summary)
    match = slim["team"]["matches"][0]

    assert "players" not in slim
    assert "player_matches" not in slim
    assert player_summary["players"][0]["player"] == "Add1t"
    assert player_matches[0]["player"] == "Add1t"
    assert match["detail_path"] == "match_details/demo3.json"
    assert "round_details" not in match
    assert match["failure_counts"]["clutch"]["1v1"] == 1
    assert match["failure_counts"]["advantage"]["5v4"] == 1
    assert details["demo3"]["match"]["round_details"] == [{"round": 1, "side": "CT", "won": True}]
    assert details["demo3"]["players"][0]["player"] == "Add1t"
