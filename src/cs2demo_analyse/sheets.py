from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from .io_utils import ensure_dir, stable_hash_rows, utc_now_iso, write_csv_dicts, write_json


class GoogleApiUnavailable(RuntimeError):
    pass


PUBLIC_SHEET_GIDS = {
    ("1FqP2Ae0Nzt1kAvW1Iz_yPk5FVI0tqmj5Hjpsp6_ANUQ", "data"): "0",
    ("1HPHNXr5r4e9y9ecgTcIJCtkuW8u8OUJOwBNbyzAw3qk", "Data"): "0",
}


def _build_services() -> tuple[Any, Any]:
    try:
        from google.auth import default
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GoogleApiUnavailable(
            "Google API dependencies are missing. Install project dependencies with `pip install -e .`."
        ) from exc

    creds, _ = default(scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ])
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return drive, sheets


def read_sheet_rows(sheet_id: str, tab: str) -> list[dict[str, str]]:
    try:
        _, sheets = _build_services()
        result = sheets.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{tab}!A:Z",
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
        values = result.get("values", [])
    except Exception:
        return read_public_sheet_rows(sheet_id, tab)
    if not values:
        return []
    header = [str(cell).strip() for cell in values[0]]
    rows: list[dict[str, str]] = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (len(header) - len(raw))
        if not any(str(cell).strip() for cell in padded):
            continue
        rows.append({header[i]: str(padded[i]).strip() for i in range(len(header))})
    return rows


def read_public_sheet_rows(sheet_id: str, tab: str) -> list[dict[str, str]]:
    import requests

    gid = PUBLIC_SHEET_GIDS.get((sheet_id, tab))
    if gid is None:
        raise GoogleApiUnavailable(f"No public CSV gid configured for sheet {sheet_id} tab {tab}")
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
    response = requests.get(url, params={"format": "csv", "gid": gid}, timeout=60)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(io.StringIO(text)) if any(row.values())]


def get_file_metadata(file_id: str) -> dict[str, str]:
    try:
        drive, _ = _build_services()
        return drive.files().get(
            fileId=file_id,
            fields="id,name,mimeType,modifiedTime,size,md5Checksum",
            supportsAllDrives=True,
        ).execute()
    except Exception:
        return {"id": file_id, "modifiedTime": "", "name": file_id}


def sync_sheets(
    output_dir: Path,
    replay_sheet_id: str,
    replay_tab: str,
    roster_sheet_id: str,
    roster_tab: str,
) -> dict[str, Any]:
    ensure_dir(output_dir / "sheets")
    specs = [
        ("replays_filter", replay_sheet_id, replay_tab),
        ("roster", roster_sheet_id, roster_tab),
    ]
    versions: dict[str, Any] = {"read_at": utc_now_iso(), "sheets": {}}
    for name, sheet_id, tab in specs:
        rows = read_sheet_rows(sheet_id, tab)
        path = output_dir / "sheets" / f"{name}.csv"
        fieldnames = list(rows[0].keys()) if rows else []
        if rows:
            write_csv_dicts(path, rows, fieldnames)
        else:
            ensure_dir(path.parent)
            with path.open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([])
        metadata = get_file_metadata(sheet_id)
        versions["sheets"][name] = {
            "file_id": sheet_id,
            "modified_time": metadata.get("modifiedTime"),
            "sheet_name": tab,
            "row_count": len(rows),
            "content_hash": stable_hash_rows(rows),
        }
    write_json(output_dir / "sheet_versions.json", versions)
    return versions
