#!/usr/bin/env python3
"""Opt-in, reversible adapter installer for tools/build_filter.py.

Default behavior is a dry run. Use --apply only after running the cache
preflight and reviewing its report against the existing builder's feed report.
A byte-for-byte backup is made before editing. This script replaces only the
fetch_feed function body and refuses unexpected source layouts.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "build_filter.py"
BACKUP_DIR = ROOT / "reports" / "maintenance-backups"
START = "def fetch_feed(feed: dict, retries: int | None = None):"
END = "def validate_feed_config(config: dict) -> None:"
REPLACEMENT = '''def fetch_feed(feed: dict, retries: int | None = None):
    """Fetch an approved reference feed through TRIHEXOMEGA's verified cache.

    Conditional 304 responses reuse a locally checksum-verified copy. Stale
    cache is diagnostic only and is never returned as coverage evidence.
    """
    from trihexomega.cache import fetch_feed_compatible
    return fetch_feed_compatible(feed, retries)

'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply the reversible one-function patch")
    parser.add_argument("--restore", action="store_true", help="restore the most recent named pre-patch backup")
    args = parser.parse_args()
    if args.apply and args.restore:
        parser.error("choose --apply or --restore, not both")
    if not BUILDER.is_file():
        print(f"ERROR: expected builder not found: {BUILDER}")
        return 2
    original = BUILDER.read_text(encoding="utf-8")
    if args.restore:
        backup = BACKUP_DIR / "build_filter.py.pre-trihexomega-cache.bak"
        if not backup.is_file():
            print("ERROR: no cache-adapter backup exists")
            return 2
        BUILDER.write_bytes(backup.read_bytes())
        print(f"Restored original builder from {backup}")
        return 0
    if START not in original or END not in original:
        print("ERROR: builder layout differs from the reviewed inherited baseline source; no changes made")
        return 2
    before, remainder = original.split(START, 1)
    _, after = remainder.split(END, 1)
    if "Cache-Control': 'no-cache'" not in original:
        print("NOTICE: builder no longer matches the reviewed fetcher signature; dry-run only")
        if not args.apply:
            return 0
        print("ERROR: refusing automatic patch against an unrecognized fetcher")
        return 2
    updated = before + REPLACEMENT + END + after
    if not args.apply:
        print("DRY RUN: would replace only fetch_feed() with trihexomega.cache.fetch_feed_compatible().")
        print("No files changed. Review cache preflight before using --apply.")
        return 0
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / "build_filter.py.pre-trihexomega-cache.bak"
    if backup.exists():
        print(f"ERROR: backup already exists; move it aside before applying: {backup}")
        return 2
    backup.write_text(original, encoding="utf-8")
    temp = BUILDER.with_name("." + BUILDER.name + ".trihexomega.tmp")
    temp.write_text(updated, encoding="utf-8")
    temp.replace(BUILDER)
    print("Applied cache adapter. Backup:", backup)
    print("Immediately run the offline tests, builder, validator, and compare feed statuses before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
