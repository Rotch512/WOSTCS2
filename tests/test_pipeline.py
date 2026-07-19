from pathlib import Path

from cs2demo_analyse.config import Settings
from cs2demo_analyse.io_utils import read_csv_dicts, read_json
from cs2demo_analyse.pipeline import sync_drive_index


def test_sync_drive_index_prefers_drive_api_over_public_scraping(tmp_path: Path, monkeypatch):
    calls = []

    def fake_drive_files():
        calls.append("drive")
        return [
            {
                "id": "drive-file",
                "name": "20260718_dust2_full_win_13_06.zip",
                "mimeType": "application/x-zip-compressed",
                "modifiedTime": "2026-07-18T14:19:54.000Z",
                "size": "171996136",
                "md5Checksum": "abc",
            }
        ]

    def fake_public_files():
        calls.append("public")
        return [
            {
                "id": "public-file",
                "name": "20260717_dust2_full_lose_09_13.zip",
                "mimeType": "application/x-zip-compressed",
                "modifiedTime": "",
                "size": "",
                "md5Checksum": "",
            }
        ]

    monkeypatch.setattr("cs2demo_analyse.pipeline.list_drive_folder_files", fake_drive_files)
    monkeypatch.setattr("cs2demo_analyse.pipeline.list_public_drive_folder_files", fake_public_files)
    monkeypatch.setattr("cs2demo_analyse.pipeline.upsert_text_file_in_folder", lambda *args, **kwargs: "manifest")

    settings = Settings(output_dir=tmp_path / "output", cache_dir=tmp_path / "cache")

    sync_drive_index(settings)

    assert calls == ["drive"]
    manifest = read_json(settings.demo_manifest_path)
    assert [item["file_id"] for item in manifest["demos"]] == ["drive-file"]
    rows = read_csv_dicts(settings.sheets_dir / "replays_filter.csv")
    assert rows[0]["match_date"] == "20260718"
