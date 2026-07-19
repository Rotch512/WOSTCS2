from __future__ import annotations

from pathlib import Path
from typing import Any

from .analytics import build_summary, split_summary_payload
from .config import ANALYSIS_MANIFEST_NAME, Settings
from .drive import download_file, list_drive_folder_files, list_public_drive_folder_files, package_path_for, upsert_text_file_in_folder
from .identity import write_identity_template
from .io_utils import ensure_dir, read_csv_dicts, utc_now_iso, write_compact_json, write_csv_dicts, read_json, write_json
from .manifest import build_manifest, manifest_to_replay_rows, remove_manifest_item, update_manifest_item
from .models import PlayerDiscovery
from .package_reader import extract_single_demo
from .parser import discover_players, parse_match_stats
from .replays import load_replays
from .roster import RosterBook, load_roster_intervals
from .sheets import read_public_sheet_rows, read_sheet_rows, sync_sheets as sync_google_sheets


def replay_csv_path(settings: Settings) -> Path:
    return settings.sheets_dir / "replays_filter.csv"


def roster_csv_path(settings: Settings) -> Path:
    return settings.sheets_dir / "roster.csv"


def sync_sheets(settings: Settings) -> None:
    sync_google_sheets(
        settings.output_dir,
        settings.replays_filter_sheet_id,
        settings.replays_filter_tab,
        settings.roster_sheet_id,
        settings.roster_tab,
    )


def sync_roster(settings: Settings) -> None:
    try:
        rows = read_public_sheet_rows(settings.roster_sheet_id, settings.roster_tab)
    except Exception:
        rows = read_sheet_rows(settings.roster_sheet_id, settings.roster_tab)
    fieldnames = list(rows[0].keys()) if rows else []
    if rows:
        write_csv_dicts(roster_csv_path(settings), rows, fieldnames)
    else:
        ensure_dir(settings.sheets_dir)
        roster_csv_path(settings).write_text("\n", encoding="utf-8")

    versions = read_json(settings.sheet_versions_path, default={}) or {}
    versions.setdefault("sheets", {})
    versions["read_at"] = utc_now_iso()
    versions["sheets"]["roster"] = {
        "file_id": settings.roster_sheet_id,
        "modified_time": "",
        "sheet_name": settings.roster_tab,
        "row_count": len(rows),
    }
    write_json(settings.sheet_versions_path, versions)


def sync_drive_index(settings: Settings) -> None:
    ensure_dir(settings.output_dir)
    try:
        files = list_drive_folder_files()
    except Exception:
        try:
            files = list_public_drive_folder_files()
        except Exception:
            previous = read_json(settings.demo_manifest_path, default={}) or {}
            if not previous.get("demos"):
                raise
            files = [
                {
                    "id": item["file_id"],
                    "name": item.get("name", item["file_id"]),
                    "mimeType": item.get("mime_type", ""),
                    "modifiedTime": item.get("modified_time", ""),
                    "size": item.get("size", ""),
                    "md5Checksum": item.get("md5", ""),
                }
                for item in previous.get("demos", [])
            ]
    files = [file for file in files if file.get("name") != ANALYSIS_MANIFEST_NAME]
    manifest = build_manifest(files, settings.demo_manifest_path)
    write_json(settings.demo_manifest_path, manifest)
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    replay_rows = manifest_to_replay_rows(manifest)
    write_csv_dicts(
        replay_csv_path(settings),
        replay_rows,
        ["file_id", "file_url", "match_date", "map_name", "roster_type", "match_result", "our_score", "opponent_score"],
    )
    versions = read_json(settings.sheet_versions_path, default={}) or {}
    versions["drive_replays"] = {
        "folder_id": "1nQ-IeHvFiuDiGI-onjeX_cclHV4yi321",
        "read_at": utc_now_iso(),
        "file_count": len(files),
        "valid_replay_count": len(replay_rows),
    }
    write_json(settings.sheet_versions_path, versions)


def load_replay_records(settings: Settings):
    return load_replays(read_csv_dicts(replay_csv_path(settings)))


def load_stats_cache(settings: Settings) -> dict[str, dict[str, Any]]:
    index = read_json(settings.player_match_stats_path, default={}) or {}
    if index.get("version") == 2 and "matches" in index:
        cache: dict[str, dict[str, Any]] = {}
        for file_id, meta in index.get("matches", {}).items():
            path = settings.output_dir / str(meta.get("path", ""))
            rows = read_json(path, default={}) or {}
            if rows:
                cache[file_id] = rows
        return cache
    return index


def write_stats_cache(settings: Settings, stats_cache: dict[str, dict[str, Any]]) -> None:
    ensure_dir(settings.match_stats_dir)
    index = {
        "version": 2,
        "updated_at": utc_now_iso(),
        "matches": {},
    }
    for file_id, rows in sorted(stats_cache.items()):
        relative_path = Path("matches") / f"{file_id}.json"
        write_compact_json(settings.output_dir / relative_path, rows)
        index["matches"][file_id] = {
            "path": relative_path.as_posix(),
            "player_count": len(rows),
        }
    write_compact_json(settings.player_match_stats_path, index)


def write_site_summary(settings: Settings, summary: dict[str, Any]) -> None:
    slim_summary, player_summary, player_matches, match_details = split_summary_payload(summary)
    ensure_dir(settings.match_details_dir)
    current_ids = set(match_details)
    for path in settings.match_details_dir.glob("*.json") if settings.match_details_dir.exists() else []:
        if path.stem not in current_ids:
            path.unlink()
    for match_id, payload in sorted(match_details.items()):
        write_compact_json(settings.match_details_dir / f"{match_id}.json", payload)
    write_compact_json(settings.summary_path, slim_summary)
    write_compact_json(settings.player_summary_path, player_summary)
    write_compact_json(settings.player_matches_path, player_matches)


def prune_to_current_replays(settings: Settings) -> None:
    if not replay_csv_path(settings).exists():
        return
    current_ids = {row["file_id"] for row in read_csv_dicts(replay_csv_path(settings)) if row.get("file_id")}

    stats_cache = {
        file_id: rows
        for file_id, rows in load_stats_cache(settings).items()
        if file_id in current_ids
    }
    write_stats_cache(settings, stats_cache)
    for path in settings.match_stats_dir.glob("*.json") if settings.match_stats_dir.exists() else []:
        if path.stem not in current_ids:
            path.unlink()
    for path in settings.match_details_dir.glob("*.json") if settings.match_details_dir.exists() else []:
        if path.stem not in current_ids:
            path.unlink()

    discovered_rows = read_json(settings.discovered_players_path, default=[]) or []
    filtered_discovered = []
    for row in discovered_rows:
        demos = [demo for demo in row.get("demos", []) if demo in current_ids]
        if not demos:
            continue
        next_row = dict(row)
        next_row["demos"] = demos
        next_row["demo_count"] = len(demos)
        filtered_discovered.append(next_row)
    if discovered_rows:
        write_json(settings.discovered_players_path, filtered_discovered)

    errors = [
        row for row in (read_json(settings.errors_path, default=[]) or [])
        if row.get("file_id") in current_ids
    ]
    write_json(settings.errors_path, errors)


def download_packages(settings: Settings) -> None:
    ensure_dir(settings.packages_dir)
    stats_cache = load_stats_cache(settings)
    for replay in load_replay_records(settings):
        manifest = read_json(settings.demo_manifest_path, default={}) or {}
        manifest_item = next((item for item in manifest.get("demos", []) if item.get("file_id") == replay.file_id), {})
        if (
            manifest_item.get("state") == "summarized"
            and stats_cache.get(replay.file_id)
        ):
            continue
        filename = manifest_item.get("name") or f"{replay.file_id}.zip"
        destination = package_path_for(replay.file_id, filename, settings.packages_dir)
        if destination.exists() and destination.stat().st_size > 0:
            next_state = manifest_item.get("state") if manifest_item.get("state") in {"extracted", "discovered", "summarized"} else "downloaded"
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                package_path=str(destination),
                state=next_state,
            )
            continue
        download_file(replay.file_id, destination)
        update_manifest_item(
            settings.demo_manifest_path,
            replay.file_id,
            package_path=str(destination),
            downloaded_at=utc_now_iso(),
            state="downloaded",
        )
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def extract_demo_for_replay(settings: Settings, replay) -> Path:
    candidates = list(settings.packages_dir.glob(f"{replay.file_id}.*"))
    if not candidates:
        raise FileNotFoundError(f"No downloaded package for replay {replay.file_id}")
    package_path = candidates[0]
    demo_dir = settings.demos_dir / replay.file_id
    existing = list(demo_dir.glob("*.dem"))
    if len(existing) == 1:
        return existing[0]
    demo_path = extract_single_demo(package_path, demo_dir)
    update_manifest_item(
        settings.demo_manifest_path,
        replay.file_id,
        demo_path=str(demo_path),
        extracted_at=utc_now_iso(),
        state="extracted",
    )
    return demo_path


def discover(settings: Settings) -> None:
    ensure_dir(settings.output_dir)
    errors = read_json(settings.errors_path, default=[])
    discovered: dict[str, PlayerDiscovery] = {}
    existing_discovered = read_json(settings.discovered_players_path, default=[]) or []
    for row in existing_discovered:
        item = discovered.setdefault(row["steam64"], PlayerDiscovery(steam64=row["steam64"]))
        item.names.update(row.get("names", []))
        item.demos.update(row.get("demos", []))
        item.maps.update(row.get("maps", []))
        item.team_names.update(row.get("team_names", []))
        if row.get("first_seen"):
            from .io_utils import parse_date

            item.first_seen = parse_date(row["first_seen"])
        if row.get("last_seen"):
            from .io_utils import parse_date

            item.last_seen = parse_date(row["last_seen"])

    manifest = read_json(settings.demo_manifest_path, default={"demos": []})
    manifest_by_id = {item["file_id"]: item for item in manifest.get("demos", [])}

    for replay in load_replay_records(settings):
        manifest_item = manifest_by_id.get(replay.file_id, {})
        if manifest_item.get("state") in {"discovered", "summarized"} and any(
            replay.file_id in item.demos for item in discovered.values()
        ):
            continue
        try:
            demo_path = extract_demo_for_replay(settings, replay)
            replay_players = discover_players(demo_path, replay)
            for steam64, item in replay_players.items():
                aggregate = discovered.setdefault(steam64, PlayerDiscovery(steam64=steam64))
                for name in item.names:
                    aggregate.names.add(name)
                for demo in item.demos:
                    aggregate.demos.add(demo)
                for map_name in item.maps:
                    aggregate.maps.add(map_name)
                for team_name in item.team_names:
                    aggregate.team_names.add(team_name)
                if item.first_seen and (aggregate.first_seen is None or item.first_seen < aggregate.first_seen):
                    aggregate.first_seen = item.first_seen
                if item.last_seen and (aggregate.last_seen is None or item.last_seen > aggregate.last_seen):
                    aggregate.last_seen = item.last_seen
        except Exception as exc:
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                state="discover_error",
                errors=[str(exc)],
            )
            errors.append({"stage": "discover", "file_id": replay.file_id, "error": str(exc)})
        else:
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                discovered_at=utc_now_iso(),
                state="discovered",
            )

    payload = []
    for steam64, item in sorted(discovered.items()):
        payload.append({
            "steam64": steam64,
            "names": sorted(item.names),
            "first_seen": item.first_seen.isoformat() if item.first_seen else None,
            "last_seen": item.last_seen.isoformat() if item.last_seen else None,
            "demos": sorted(item.demos),
            "maps": sorted(item.maps),
            "team_names": sorted(item.team_names),
            "demo_count": len(item.demos),
        })
    write_json(settings.discovered_players_path, payload)
    write_json(settings.errors_path, errors)
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def init_identity(settings: Settings) -> None:
    discovered_players = read_json(settings.discovered_players_path, default=[])
    write_identity_template(settings.identity_path, discovered_players)


def summarize(settings: Settings) -> None:
    errors = read_json(settings.errors_path, default=[])
    roster_book = RosterBook(load_roster_intervals(read_csv_dicts(roster_csv_path(settings))))
    stats_cache = load_stats_cache(settings)
    match_rows = []

    for replay in load_replay_records(settings):
        try:
            cached_rows = stats_cache.get(replay.file_id, {})
            needs_reparse = not cached_rows or any(
                "clutch_broad_losses" not in row
                or "clutch_rounds" not in row
                or "clutch_failures" not in row
                or "opponent_flashed_count" not in row
                or "advantage_failures" not in row
                or "round_details" not in row
                or any("buy" not in item for item in row.get("round_details", []) or [])
                or "he_damage" not in row
                or "fire_damage" not in row
                or (not row.get("rounds") and (row.get("kills") or row.get("deaths") or row.get("assists") or row.get("damage")))
                for row in cached_rows.values()
            )
            if needs_reparse:
                demo_path = extract_demo_for_replay(settings, replay)
                per_player = parse_match_stats(demo_path, replay)
                stats_cache[replay.file_id] = {
                    steam64: stats.__dict__
                    for steam64, stats in per_player.items()
                }
            for steam64, stats_row in stats_cache[replay.file_id].items():
                active = roster_book.active_identity_for_steam(steam64, replay.match_date)
                if not active:
                    continue
                canonical_player, status = active
                from .models import PlayerMatchStats

                stats = PlayerMatchStats(**stats_row)
                match_rows.append((replay, canonical_player, status, stats))
        except Exception as exc:
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                state="summarize_error",
                errors=[str(exc)],
            )
            errors.append({"stage": "summarize", "file_id": replay.file_id, "error": str(exc)})
        else:
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                summarized_at=utc_now_iso(),
                state="summarized",
            )

    summary = build_summary(match_rows)
    summary["sheet_versions"] = read_json(settings.sheet_versions_path, default={})
    write_stats_cache(settings, stats_cache)
    write_site_summary(settings, summary)
    write_json(settings.errors_path, errors)
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def run_incremental(settings: Settings) -> None:
    sync_roster(settings)
    sync_drive_index(settings)
    prune_to_current_replays(settings)
    download_packages(settings)
    discover(settings)
    summarize(settings)


def delete_demo(settings: Settings, selector: str, remove_cached_files: bool = False) -> dict[str, Any]:
    removed = remove_manifest_item(settings.demo_manifest_path, selector)
    file_id = removed["file_id"]

    replay_rows = [
        row for row in read_csv_dicts(replay_csv_path(settings))
        if row.get("file_id") != file_id
    ] if replay_csv_path(settings).exists() else []
    write_csv_dicts(
        replay_csv_path(settings),
        replay_rows,
        ["file_id", "file_url", "match_date", "map_name", "roster_type", "match_result", "our_score", "opponent_score"],
    )

    stats_cache = load_stats_cache(settings)
    stats_cache.pop(file_id, None)
    stats_path = settings.match_stats_dir / f"{file_id}.json"
    if stats_path.exists():
        stats_path.unlink()
    detail_path = settings.match_details_dir / f"{file_id}.json"
    if detail_path.exists():
        detail_path.unlink()
    write_stats_cache(settings, stats_cache)

    discovered_rows = read_json(settings.discovered_players_path, default=[]) or []
    filtered_discovered = []
    for row in discovered_rows:
        demos = [demo for demo in row.get("demos", []) if demo != file_id]
        if not demos:
            continue
        next_row = dict(row)
        next_row["demos"] = demos
        next_row["demo_count"] = len(demos)
        filtered_discovered.append(next_row)
    write_json(settings.discovered_players_path, filtered_discovered)

    errors = [
        row for row in (read_json(settings.errors_path, default=[]) or [])
        if row.get("file_id") != file_id
    ]
    write_json(settings.errors_path, errors)

    if remove_cached_files:
        for path_text in (removed.get("package_path"), removed.get("demo_path")):
            if path_text:
                path = Path(path_text)
                if path.exists() and path.is_file():
                    path.unlink()
        demo_dir = settings.demos_dir / file_id
        if demo_dir.exists():
            for child in demo_dir.glob("*"):
                if child.is_file():
                    child.unlink()
            try:
                demo_dir.rmdir()
            except OSError:
                pass

    summarize(settings)
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return removed
