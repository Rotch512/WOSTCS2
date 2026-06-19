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
