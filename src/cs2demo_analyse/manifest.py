from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io_utils import read_json, utc_now_iso, write_json

DEMO_NAME_RE = re.compile(
    r"^(?P<date>\d{8})_(?P<map>[a-z0-9]+)_(?P<roster>full|subbed|mixed)_"
    r"(?P<result>win|lose|draw)_(?P<our>\d{1,2})_(?P<opp>\d{1,2})(?:\.[^.]+)?$",
    re.IGNORECASE,
)


def parse_demo_name(name: str) -> dict[str, str]:
    match = DEMO_NAME_RE.match(name)
    if not match:
        raise ValueError(f"Demo package name does not match convention: {name}")
    groups = match.groupdict()
    return {
        "match_date": groups["date"],
        "map_name": groups["map"].lower(),
        "roster_type": groups["roster"].lower(),
        "match_result": groups["result"].lower(),
        "our_score": str(int(groups["our"])),
        "opponent_score": str(int(groups["opp"])),
    }


def manifest_to_replay_rows(manifest: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in manifest.get("demos", []):
        parsed = item.get("parsed") or {}
        if item.get("state") == "invalid_name" or not parsed:
            continue
        rows.append({
            "file_id": item["file_id"],
            "file_url": item.get("file_url", ""),
            "match_date": parsed["match_date"],
            "map_name": parsed["map_name"],
            "roster_type": parsed["roster_type"],
            "match_result": parsed["match_result"],
            "our_score": parsed["our_score"],
            "opponent_score": parsed["opponent_score"],
        })
    return rows


def build_manifest(files: list[dict[str, str]], previous_path: Path) -> dict[str, Any]:
    previous = read_json(previous_path, default={}) or {}
    previous_by_id = {item["file_id"]: item for item in previous.get("demos", [])}
    demos: list[dict[str, Any]] = []
    for file in files:
        file_id = file["id"]
        name = file.get("name") or file.get("title") or file_id
        previous_item = previous_by_id.get(file_id, {})
        item: dict[str, Any] = {
            "file_id": file_id,
            "name": name,
            "file_url": f"https://drive.google.com/file/d/{file_id}/view",
            "mime_type": file.get("mimeType") or file.get("mime_type") or "",
            "modified_time": file.get("modifiedTime") or file.get("modified_time") or "",
            "size": str(file.get("size") or ""),
            "md5": file.get("md5Checksum") or "",
            "package_path": previous_item.get("package_path", ""),
            "demo_path": previous_item.get("demo_path", ""),
            "downloaded_at": previous_item.get("downloaded_at", ""),
            "extracted_at": previous_item.get("extracted_at", ""),
            "discovered_at": previous_item.get("discovered_at", ""),
            "summarized_at": previous_item.get("summarized_at", ""),
            "state": previous_item.get("state", "pending"),
            "errors": previous_item.get("errors", []),
            "warnings": previous_item.get("warnings", []),
        }
        old_fingerprint = (
            previous_item.get("modified_time"),
            previous_item.get("size"),
            previous_item.get("md5"),
        )
        new_fingerprint = (item["modified_time"], item["size"], item["md5"])
        if previous_item and old_fingerprint != new_fingerprint:
            item.update({
                "package_path": "",
                "demo_path": "",
                "downloaded_at": "",
                "extracted_at": "",
                "discovered_at": "",
                "summarized_at": "",
                "state": "changed",
                "errors": [],
                "warnings": [],
            })
        try:
            item["parsed"] = parse_demo_name(name)
        except ValueError as exc:
            item["parsed"] = {}
            item["state"] = "invalid_name"
            item["errors"] = [str(exc)]
        demos.append(item)
    return {"updated_at": utc_now_iso(), "demos": demos}


def update_manifest_item(path: Path, file_id: str, **updates: Any) -> None:
    manifest = read_json(path, default={"demos": []})
    for item in manifest.get("demos", []):
        if item.get("file_id") == file_id:
            item.update(updates)
            break
    manifest["updated_at"] = utc_now_iso()
    write_json(path, manifest)
