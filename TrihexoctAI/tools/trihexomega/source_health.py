#!/usr/bin/env python3
"""Deterministic, privacy-minimizing reference-source health analytics.

Health scores are diagnostics only. This module never removes, disables,
reweights, or replaces an approved source and never grants coverage credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make direct `python tools/trihexomega/<module>.py` invocation work exactly
# like package execution and GitHub Actions commands. The package root is
# tools/, one directory above this module's folder.
_TOOLS_ROOT = str(Path(__file__).resolve().parents[1])
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)
from typing import Any

from trihexomega.cache import atomic_json


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_id(name: str, url: str) -> str:
    return hashlib.sha256((name + "\0" + url).encode("utf-8")).hexdigest()[:20]


def evaluate_health(feed_report: dict[str, Any], registry: dict[str, Any], history: dict[str, Any] | None = None,
                    max_runs: int = 30) -> tuple[dict[str, Any], dict[str, Any]]:
    history = history or {"schema_version": 1, "sources": {}}
    if history.get("schema_version") != 1 or not isinstance(history.get("sources"), dict):
        raise ValueError("source-health history schema is invalid")
    feeds_by_name = {str(feed["name"]): feed for feed in registry.get("feeds", [])}
    sources = json.loads(json.dumps(history["sources"]))
    rows = []
    for result in feed_report.get("feeds", []):
        name = str(result.get("name", "unknown"))
        feed = feeds_by_name.get(name, {})
        url = str(feed.get("url", ""))
        sid = source_id(name, url)
        old = sources.get(sid, {"name": name, "observations": [], "latency_ewma_seconds": None})
        success = bool(result.get("ok") and result.get("coverage_eligible"))
        latency = float(result.get("duration_seconds", 0.0) or 0.0)
        observations = list(old.get("observations", []))[-(max_runs - 1):]
        observations.append({"at_utc": utc_now(), "success": success,
                             "cache_status": str(result.get("cache_status", "unknown")),
                             "attempts": int(result.get("attempts", 0) or 0),
                             "latency_seconds": round(max(0.0, latency), 3)})
        rate = sum(1 for item in observations if item.get("success")) / max(1, len(observations))
        tail = observations[-5:]
        failure_streak = 0
        for item in reversed(observations):
            if item.get("success"):
                break
            failure_streak += 1
        prior_ewma = old.get("latency_ewma_seconds")
        ewma = latency if prior_ewma is None and success else prior_ewma
        if success:
            ewma = latency if ewma is None else (0.30 * latency + 0.70 * float(ewma))
        # Avoid declaring a source unreliable from one transient event or a
        # tiny sample. Repeated failure or sustained low success is required.
        if len(observations) >= 3 and (failure_streak >= 3 or rate < 0.60):
            status = "unreliable"
        elif failure_streak > 0 or (len(observations) >= 3 and rate < 0.90):
            status = "degraded"
        else:
            status = "healthy" if len(observations) >= 3 else "warming_up"
        publisher_id = str(feed.get("publisher_id") or f"unclassified-{sid}").lower().strip()
        sources[sid] = {"name": name, "publisher_id": publisher_id,
                        "publisher_identity_classified": bool(feed.get("publisher_id")),
                        "source_host": (url.split("/")[2] if "://" in url else ""),
                        "observations": observations, "latency_ewma_seconds": round(float(ewma), 3) if ewma is not None else None,
                        "success_rate": round(rate, 4), "failure_streak": failure_streak, "status": status}
        rows.append({"id": sid, "name": name, "publisher_id": publisher_id,
                     "publisher_identity_classified": bool(feed.get("publisher_id")), "status": status,
                     "observations": len(observations), "success_rate": round(rate, 4),
                     "failure_streak": failure_streak,
                     "latency_ewma_seconds": sources[sid]["latency_ewma_seconds"],
                     "latest_cache_status": observations[-1]["cache_status"]})
    rows.sort(key=lambda x: (x["status"], x["name"].casefold()))
    publisher_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        publisher_groups.setdefault(row["publisher_id"], []).append(row)
    publisher_rows = []
    for publisher_id, members in sorted(publisher_groups.items()):
        publisher_rows.append({
            "publisher_id": publisher_id,
            "feed_count": len(members),
            "healthy_or_warming": sum(x["status"] in {"healthy", "warming_up"} for x in members),
            "degraded": sum(x["status"] == "degraded" for x in members),
            "unreliable": sum(x["status"] == "unreliable" for x in members),
            "mean_success_rate": round(sum(x["success_rate"] for x in members) / len(members), 4),
            "feed_names": sorted(x["name"] for x in members),
        })
    summary = {"schema_version": 2, "generated_at_utc": utc_now(), "mode": "diagnostic_only_source_and_publisher_health",
               "source_count": len(rows), "publisher_group_count": len(publisher_rows),
               "healthy_or_warming": sum(x["status"] in {"healthy", "warming_up"} for x in rows),
               "degraded": sum(x["status"] == "degraded" for x in rows),
               "unreliable": sum(x["status"] == "unreliable" for x in rows),
               "sources": rows, "publisher_groups": publisher_rows,
               "publisher_ids_are_curated_labels_not_verified_ownership": True,
               "policy": "Health is diagnostic only: it never automatically removes, disables, reweights, or replaces a feed, never changes publisher identity, and never creates coverage credit."}
    return summary, {"schema_version": 1, "sources": sources, "updated_at_utc": utc_now()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed-report", type=Path, default=Path("reports/trihexomega-feed-cache-report.json"))
    parser.add_argument("--registry", type=Path, default=Path("config/reference_feeds.json"))
    parser.add_argument("--history", type=Path, default=Path("reports/trihexomega-source-health-history.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/trihexomega-source-health.json"))
    args = parser.parse_args()
    history = json.loads(args.history.read_text(encoding="utf-8")) if args.history.exists() else None
    summary, updated = evaluate_health(json.loads(args.feed_report.read_text(encoding="utf-8")),
                                       json.loads(args.registry.read_text(encoding="utf-8")), history)
    atomic_json(args.output, summary)
    atomic_json(args.history, updated)
    print(json.dumps({k: summary[k] for k in ("source_count", "healthy_or_warming", "degraded", "unreliable")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
