from cs2demo_analyse.io_utils import read_json, write_json
from cs2demo_analyse.manifest import parse_demo_name, remove_manifest_item


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


def test_remove_manifest_item_by_file_name(tmp_path):
    path = tmp_path / "demo_manifest.json"
    write_json(path, {
        "demos": [
            {"file_id": "keep", "name": "20260601_mirage_full_win_13_11.zip"},
            {"file_id": "drop", "name": "20260602_nuke_full_lose_07_13.zip"},
        ]
    })

    removed = remove_manifest_item(path, "20260602_nuke_full_lose_07_13.zip")

    assert removed["file_id"] == "drop"
    manifest = read_json(path)
    assert [item["file_id"] for item in manifest["demos"]] == ["keep"]
