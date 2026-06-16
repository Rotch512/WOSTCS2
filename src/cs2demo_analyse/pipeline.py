from __future__ import annotations

from pathlib import Path

from .analytics import build_summary
from .config import ANALYSIS_MANIFEST_NAME, Settings
from .drive import download_file, download_text_file, find_file_in_folder, list_drive_folder_files, package_path_for, upsert_text_file_in_folder
from .identity import write_identity_template
from .io_utils import ensure_dir, read_csv_dicts, utc_now_iso, write_csv_dicts, read_json, write_json
from .manifest import build_manifest, manifest_to_replay_rows, update_manifest_item
from .models import PlayerDiscovery
from .package_reader import extract_single_demo
from .parser import discover_players, map_name_from_demo_filename, parse_actual_match_metadata, parse_match_stats
from .replays import load_replays
from .roster import RosterBook, is_counted_status, load_roster_intervals
from .sheets import sync_sheets as sync_google_sheets


def replay_csv_path(settings: Settings) -> Path:
    return settings.sheets_dir / "replays_filter.csv"


def roster_csv_path(settings: Settings) -> Path:
    return settings.sheets_dir / "roster.csv"


def sync_sheets(settings: Settings) -> None:
    print("[cs2demo] Syncing Google Sheets", flush=True)
    sync_google_sheets(
        settings.output_dir,
        settings.replays_filter_sheet_id,
        settings.replays_filter_tab,
        settings.roster_sheet_id,
        settings.roster_tab,
    )


def sync_drive_index(settings: Settings) -> None:
    print("[cs2demo] Syncing Google Drive replay index", flush=True)
    ensure_dir(settings.output_dir)
    try:
        remote_manifest = find_file_in_folder(ANALYSIS_MANIFEST_NAME)
        if remote_manifest:
            settings.demo_manifest_path.write_text(download_text_file(remote_manifest["id"]), encoding="utf-8")
    except Exception:
        pass
    try:
        files = list_drive_folder_files()
    except Exception:
        rows = read_csv_dicts(replay_csv_path(settings))
        files = []
        for row in rows:
            name = (
                f"{row['match_date']}_{row['map_name']}_{row['roster_type']}_{row['match_result']}_"
                f"{int(row['our_score']):02d}_{int(row['opponent_score']):02d}.zip"
            )
            package_candidates = list(settings.packages_dir.glob(f"{row['file_id']}.*"))
            files.append({
                "id": row["file_id"],
                "name": name,
                "mimeType": "application/x-zip-compressed",
                "modifiedTime": "",
                "size": str(package_candidates[0].stat().st_size) if package_candidates else "",
                "md5Checksum": "",
            })
    manifest = build_manifest(files, settings.demo_manifest_path)
    write_json(settings.demo_manifest_path, manifest)
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    replay_rows = manifest_to_replay_rows(manifest)
    if replay_rows:
        write_csv_dicts(
            replay_csv_path(settings),
            replay_rows,
            ["file_id", "file_url", "match_date", "map_name", "roster_type", "match_result", "our_score", "opponent_score"],
        )


def load_replay_records(settings: Settings):
    return load_replays(read_csv_dicts(replay_csv_path(settings)))


def download_packages(settings: Settings) -> None:
    print("[cs2demo] Downloading missing demo packages", flush=True)
    ensure_dir(settings.packages_dir)
    stats_cache = read_json(settings.player_match_stats_path, default={}) or {}
    for replay in load_replay_records(settings):
        manifest = read_json(settings.demo_manifest_path, default={}) or {}
        manifest_item = next((item for item in manifest.get("demos", []) if item.get("file_id") == replay.file_id), {})
        if manifest_item.get("state") == "summarized" and stats_cache.get(replay.file_id):
            print(f"[cs2demo] Package cached: {manifest_item.get('name') or replay.file_id}", flush=True)
            continue
        filename = manifest_item.get("name") or f"{replay.file_id}.zip"
        destination = package_path_for(replay.file_id, filename, settings.packages_dir)
        if destination.exists() and destination.stat().st_size > 0:
            print(f"[cs2demo] Package already downloaded: {filename}", flush=True)
            next_state = manifest_item.get("state") if manifest_item.get("state") in {"extracted", "discovered", "summarized"} else "downloaded"
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                package_path=str(destination),
                state=next_state,
            )
            continue
        print(f"[cs2demo] Downloading package: {filename}", flush=True)
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


def active_roster_steam64s(settings: Settings, replay) -> set[str]:
    active: set[str] = set()
    for interval in load_roster_intervals(read_csv_dicts(roster_csv_path(settings))):
        if is_counted_status(interval.status) and interval.contains(replay.match_date):
            active.add(interval.steam64)
    return active


def sync_demo_metadata(settings: Settings) -> None:
    print("[cs2demo] Validating demo metadata against extracted files", flush=True)
    stats_cache = read_json(settings.player_match_stats_path, default={}) or {}
    manifest_changed = False
    stats_changed = False
    discovery_changed = False

    for replay in load_replay_records(settings):
        try:
            demo_path = extract_demo_for_replay(settings, replay)
            actual = parse_actual_match_metadata(demo_path, replay, active_roster_steam64s(settings, replay))
        except Exception as exc:
            update_manifest_item(
                settings.demo_manifest_path,
                replay.file_id,
                warnings=[f"Unable to validate demo metadata: {exc}"],
            )
            continue

        manifest = read_json(settings.demo_manifest_path, default={"demos": []}) or {"demos": []}
        item = next((row for row in manifest.get("demos", []) if row.get("file_id") == replay.file_id), {})
        previous = item.get("parsed") or {}
        if previous == actual:
            continue

        warning = (
            "Demo metadata differs from Sheet/Drive filename: "
            f"sheet={previous}, actual={actual}."
        )
        print(f"[cs2demo] WARNING: {warning}", flush=True)
        update_manifest_item(
            settings.demo_manifest_path,
            replay.file_id,
            parsed=actual,
            warnings=[warning],
            discovered_at="",
            summarized_at="",
            state="extracted",
        )
        manifest_changed = True
        discovery_changed = True
        if replay.file_id in stats_cache:
            del stats_cache[replay.file_id]
            stats_changed = True

    if stats_changed:
        write_json(settings.player_match_stats_path, stats_cache)
    if discovery_changed:
        settings.discovered_players_path.write_text("[]\n", encoding="utf-8")
        manifest = read_json(settings.demo_manifest_path, default={"demos": []}) or {"demos": []}
        for item in manifest.get("demos", []):
            if item.get("state") == "summarized":
                update_manifest_item(
                    settings.demo_manifest_path,
                    item["file_id"],
                    discovered_at="",
                    summarized_at="",
                    state="extracted",
                )
    if manifest_changed:
        manifest = read_json(settings.demo_manifest_path, default={"demos": []}) or {"demos": []}
        replay_rows = manifest_to_replay_rows(manifest)
        if replay_rows:
            write_csv_dicts(
                replay_csv_path(settings),
                replay_rows,
                ["file_id", "file_url", "match_date", "map_name", "roster_type", "match_result", "our_score", "opponent_score"],
            )


def extract_demo_for_replay(settings: Settings, replay) -> Path:
    candidates = list(settings.packages_dir.glob(f"{replay.file_id}.*"))
    if not candidates:
        raise FileNotFoundError(f"No downloaded package for replay {replay.file_id}")
    package_path = candidates[0]
    demo_dir = settings.demos_dir / replay.file_id
    existing = list(demo_dir.glob("*.dem"))
    if len(existing) == 1:
        validate_demo_filename(settings, replay, existing[0])
        return existing[0]
    demo_path = extract_single_demo(package_path, demo_dir)
    validate_demo_filename(settings, replay, demo_path)
    update_manifest_item(
        settings.demo_manifest_path,
        replay.file_id,
        demo_path=str(demo_path),
        extracted_at=utc_now_iso(),
        state="extracted",
    )
    return demo_path


def validate_demo_filename(settings: Settings, replay, demo_path: Path) -> None:
    demo_map = map_name_from_demo_filename(demo_path)
    if not demo_map or demo_map == replay.map_name:
        update_manifest_item(settings.demo_manifest_path, replay.file_id, warnings=[])
        return
    warning = (
        f"Demo filename map '{demo_map}' does not match replay metadata map "
        f"'{replay.map_name}' for {demo_path.name}."
    )
    print(f"[cs2demo] WARNING: {warning}", flush=True)
    update_manifest_item(settings.demo_manifest_path, replay.file_id, warnings=[warning])


def discover(settings: Settings) -> None:
    print("[cs2demo] Discovering players from demos", flush=True)
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
    print("[cs2demo] Writing player identity template", flush=True)
    discovered_players = read_json(settings.discovered_players_path, default=[])
    write_identity_template(settings.identity_path, discovered_players)


def summarize(settings: Settings) -> None:
    print("[cs2demo] Summarizing player and team analytics", flush=True)
    errors = read_json(settings.errors_path, default=[])
    roster_book = RosterBook(load_roster_intervals(read_csv_dicts(roster_csv_path(settings))))
    stats_cache = read_json(settings.player_match_stats_path, default={}) or {}
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
    write_json(settings.player_match_stats_path, stats_cache)
    write_json(settings.summary_path, summary)
    write_json(settings.errors_path, errors)
    try:
        upsert_text_file_in_folder(ANALYSIS_MANIFEST_NAME, settings.demo_manifest_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def run_incremental(settings: Settings) -> None:
    sync_sheets(settings)
    sync_drive_index(settings)
    download_packages(settings)
    sync_demo_metadata(settings)
    discover(settings)
    summarize(settings)
