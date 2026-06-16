from datetime import date

from cs2demo_analyse.analytics import build_summary
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
