from cs2demo_analyse.manifest import parse_demo_name


def test_parse_demo_name_supports_draw_and_scores():
    parsed = parse_demo_name("20260605_dust2_subbed_draw_12_12.zip")

    assert parsed == {
        "match_date": "20260605",
        "map_name": "dust2",
        "roster_type": "subbed",
        "match_result": "draw",
        "our_score": "12",
        "opponent_score": "12",
    }

