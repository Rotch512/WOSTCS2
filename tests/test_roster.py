from datetime import date

from cs2demo_analyse.roster import RosterBook, load_roster_intervals


def test_roster_counts_starter_standin_and_benched_but_not_left():
    rows = [
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-5-30", "End": "2026-6-2", "Status": "Starter"},
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-6-2", "End": "2026-6-4", "Status": "Benched"},
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-6-4", "End": "", "Status": "Left"},
        {"Player": "Yab66", "SteamID": "766", "Start": "2026-5-29", "End": "", "Status": "Stand-in"},
    ]
    book = RosterBook(load_roster_intervals(rows))

    assert book.is_active_player("qiuda", date(2026, 5, 30))
    assert book.is_active_player("qiuda", date(2026, 6, 3))
    assert not book.is_active_player("qiuda", date(2026, 6, 4))
    assert book.is_active_player("Yab66", date(2026, 6, 12))
    assert book.active_identity_for_steam("765", date(2026, 6, 3)) == ("qiuda", "Benched")


def test_missing_end_infers_status_transitions_in_date_order():
    rows = [
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-9-14", "Status": "Starter"},
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-6-4", "Status": "Left"},
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-5-30", "Status": "Starter"},
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-6-2", "Status": "Benched"},
        {"Player": "qiuda", "SteamID": "765", "Start": "2026-9-24", "Status": "Benched"},
    ]
    book = RosterBook(load_roster_intervals(rows))
    assert book.status_for("qiuda", date(2026, 6, 1)) == "Starter"
    assert book.status_for("qiuda", date(2026, 6, 2)) == "Benched"
    assert book.active_identity_for_steam("765", date(2026, 6, 4)) is None
    assert not book.is_active_player("qiuda", date(2026, 9, 13))
    assert book.status_for("qiuda", date(2026, 9, 14)) == "Starter"
    assert book.status_for("qiuda", date(2026, 9, 24)) == "Benched"


def test_explicit_end_and_same_day_status_precedence():
    rows = [
        {"Player": "p", "SteamID": "1", "Start": "2026-5-1", "End": "2026-5-3", "Status": "Starter"},
        {"Player": "p", "SteamID": "1", "Start": "2026-5-5", "Status": "Starter"},
        {"Player": "p", "SteamID": "1", "Start": "2026-5-5", "Status": "Benched"},
    ]
    book = RosterBook(load_roster_intervals(rows))
    assert not book.is_active_player("p", date(2026, 5, 4))
    assert book.status_for("p", date(2026, 5, 5)) == "Benched"


def test_change_records_do_not_close_status_and_expire_at_next_change():
    rows = [
        {"Player": "p", "SteamID": "1", "Start": "2026-5-1", "Status": "Starter"},
        {"Player": "p", "SteamID": "2", "Start": "2026-5-2", "Status": "Change"},
        {"Player": "p", "SteamID": "3", "Start": "2026-5-3", "Status": "Change"},
        {"Player": "p", "SteamID": "1", "Start": "2026-5-4", "Status": "Benched"},
        {"Player": "p", "SteamID": "1", "Start": "2026-5-5", "Status": "Left"},
    ]
    book = RosterBook(load_roster_intervals(rows))
    assert book.active_identity_for_steam("2", date(2026, 5, 2)) == ("p", "Starter")
    assert book.active_identity_for_steam("2", date(2026, 5, 3)) is None
    assert book.active_identity_for_steam("3", date(2026, 5, 3)) == ("p", "Starter")
    assert book.active_identity_for_steam("3", date(2026, 5, 4)) == ("p", "Benched")
    assert book.active_identity_for_steam("3", date(2026, 5, 5)) is None
