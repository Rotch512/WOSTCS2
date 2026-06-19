from __future__ import annotations

import argparse
from pathlib import Path

from .config import Settings
from .pipeline import delete_demo, download_packages, discover, init_identity, run_incremental, summarize, sync_drive_index, sync_roster, sync_sheets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cs2demo")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--cache-dir", default=".cache/cs2demo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync-sheets")
    sub.add_parser("sync-roster")
    sub.add_parser("sync-drive-index")
    sub.add_parser("download")
    sub.add_parser("discover")
    sub.add_parser("init-identity")
    sub.add_parser("summarize")
    sub.add_parser("run")
    sub.add_parser("all")
    delete_parser = sub.add_parser("delete-demo")
    delete_parser.add_argument("selector", help="Drive file_id or exact demo package file name to remove from published data")
    delete_parser.add_argument("--delete-cache", action="store_true", help="Also delete local downloaded package/demo cache for this file")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(output_dir=Path(args.output_dir), cache_dir=Path(args.cache_dir))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_args(args)
    if args.command == "sync-sheets":
        sync_sheets(settings)
    elif args.command == "sync-roster":
        sync_roster(settings)
    elif args.command == "sync-drive-index":
        sync_drive_index(settings)
    elif args.command == "download":
        download_packages(settings)
    elif args.command == "discover":
        discover(settings)
    elif args.command == "init-identity":
        init_identity(settings)
    elif args.command == "summarize":
        summarize(settings)
    elif args.command == "run":
        run_incremental(settings)
    elif args.command == "all":
        run_incremental(settings)
    elif args.command == "delete-demo":
        removed = delete_demo(settings, args.selector, remove_cached_files=args.delete_cache)
        print(f"Deleted demo from generated data: {removed.get('file_id')} {removed.get('name', '')}".strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
