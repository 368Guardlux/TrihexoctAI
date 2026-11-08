#!/usr/bin/env python3
"""Conservative, delta-based candidate discovery from validated reference feeds.

This module never edits source modules or the published filter list. It only
creates advisory proposals from *newly observed exact* third-party host rules
that appear in at least two distinct registry-declared publisher groups.
URL-indicator feeds, domain-only feeds, stale cache, and broad/complex rules
are intentionally excluded. Publisher IDs are curated grouping metadata, not
cryptographic proof of ownership, editorial independence, or correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make direct `python tools/trihexomega/<module>.py` invocation work exactly
# like package execution and GitHub Actions commands. The package root is
# tools/, one directory above this module's folder.
_TOOLS_ROOT = str(Path(__file__).resolve().parents[1])
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)
from typing import Any
from urllib.parse import urlparse

from trihexomega.cache import atomic_json, load_cache, validate_bytes, validate_registry_config

RULE_RE = re.compile(r"^\|\|(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})\^\$third-party$", re.I)
PROTECTED_SUFFIXES = (
    "google.com", "googleapis.com", "googleusercontent.com", "gstatic.com",
    "youtube.com", "youtube-nocookie.com", "microsoft.com", "microsoftonline.com",
    "live.com", "office.com", "apple.com", "icloud.com", "amazon.com",
    "amazonaws.com", "cloudfront.net", "cloudflare.com", "github.com",
    "githubusercontent.com", "mozilla.org", "brave.com", "wikipedia.org",
    "paypal.com", "stripe.com", "visa.com", "mastercard.com", "bankofamerica.com",
    "chase.com", "wellsfargo.com", "okta.com", "auth0.com", "salesforce.com",
    "adobe.com", "akamai.net", "akamaized.net", "fastly.net", "jsdelivr.net",
    "unpkg.com", "cdnjs.com", "wordpress.com", "blogspot.com", "medium.com",
)
SHARED_HOSTING_SUFFIXES = (
    "github.io", "pages.dev", "workers.dev", "vercel.app", "netlify.app",
    "web.app", "firebaseapp.com", "azurewebsites.net", "herokuapp.com",
    "cloudfunctions.net", "s3.amazonaws.com", "storage.googleapis.com",
    "amazonaws.com", "cloudfront.net", "blogspot.com", "wordpress.com",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def suffix_match(host: str, suffixes: tuple[str, ...]) -> str | None:
    host = host.lower().rstrip(".")
    for suffix in suffixes:
        if host == suffix or host.endswith("." + suffix):
            return suffix
    return None


def classify_rule(line: str) -> tuple[str, str] | None:
    """Accept only exact host-anchored third-party network rules."""
    match = RULE_RE.fullmatch(line.strip())
    if not match:
        return None
    host = match.group("host").lower().rstrip(".")
    if suffix_match(host, PROTECTED_SUFFIXES):
        return None
    return host, "network"


def local_rule_set(modules_dir: Path) -> set[str]:
    rules: set[str] = set()
    for path in sorted(modules_dir.glob("*.txt"), key=lambda p: p.name.casefold()):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        for raw in text.splitlines():
            line = raw.strip()
            if line and not line.startswith("!"):
                rules.add(line)
    return rules


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 2, "feeds": {}, "observations": {}, "reviewed": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise ValueError("candidate-discovery baseline schema is invalid; no baseline was changed")
    for key in ("feeds", "observations", "reviewed"):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"candidate-discovery baseline field {key} must be an object")
    return data


def discover_candidates(registry_path: Path, feed_report_path: Path, cache_dir: Path,
                         modules_dir: Path, baseline_path: Path, output_path: Path,
                         min_publishers: int = 2, max_candidates: int = 8,
                         observation_days: int = 45) -> dict[str, Any]:
    if min_publishers < 2 or min_publishers > 8:
        raise ValueError("candidate discovery requires 2..8 curated publisher groups")
    if max_candidates < 1 or max_candidates > 8:
        raise ValueError("candidate discovery is capped at eight candidates per cycle")
    if not 1 <= observation_days <= 180:
        raise ValueError("candidate observation window must be between 1 and 180 days")
    registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
    feeds = validate_registry_config(registry_data)
    feed_report = json.loads(feed_report_path.read_text(encoding="utf-8"))
    report_rows = {str(row.get("name")): row for row in feed_report.get("feeds", []) if isinstance(row, dict)}
    baseline = load_baseline(baseline_path)
    publisher_by_source_id = {
        fingerprint(str(feed["name"]) + "\0" + str(feed["url"]))[:16]: str(feed.get("publisher_id", "")).strip().lower()
        for feed in feeds if feed.get("publisher_id")
    }
    # Migrate alpha.1/early-alpha.3 observations that recorded hostnames but
    # not registry publisher IDs. Unknown identities remain unclassified.
    for observation in baseline["observations"].values():
        for source in observation.get("sources", []) if isinstance(observation, dict) else []:
            mapped = publisher_by_source_id.get(str(source.get("id", "")))
            if mapped:
                source["publisher_id"] = mapped
    local_rules = local_rule_set(modules_dir)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, min(observation_days, 180)))
    observations: dict[str, Any] = baseline["observations"]
    updated_feeds = dict(baseline["feeds"])
    seeded = 0
    examined = 0
    rejected_shared = 0
    rejected_existing = 0
    successful_feeds = 0
    source_errors: list[dict[str, str]] = []

    for feed in feeds:
        name = str(feed["name"])
        row = report_rows.get(name, {})
        if feed.get("format") != "adblock" or not row.get("ok") or not row.get("coverage_eligible"):
            continue
        body, state = load_cache(cache_dir, name, str(feed["url"]))
        if body is None or state is None or state.get("sha256") != row.get("sha256"):
            source_errors.append({"feed": name, "reason": "no matching verified cache body; source excluded"})
            continue
        try:
            text, _ = validate_bytes(body, feed)
        except Exception as exc:
            source_errors.append({"feed": name, "reason": f"cached body failed revalidation: {type(exc).__name__}"})
            continue
        successful_feeds += 1
        feed_host = (urlparse(str(feed["url"])).hostname or "").lower().rstrip(".")
        publisher_id = str(feed.get("publisher_id") or "").lower().strip()
        if not publisher_id:
            source_errors.append({"feed": name, "reason": "missing registry-declared publisher_id; source can update baseline but cannot corroborate candidates"})
        current_rules: dict[str, tuple[str, str]] = {}
        for raw in text.splitlines():
            line = raw.strip()
            parsed = classify_rule(line)
            if not parsed:
                continue
            host, category = parsed
            examined += 1
            rule_fp = fingerprint(line)
            current_rules[rule_fp] = (line, host)

        feed_key = fingerprint(name + "\0" + str(feed["url"]))
        previous = updated_feeds.get(feed_key)
        previous_fps = set(previous.get("rule_fingerprints", [])) if isinstance(previous, dict) else None
        if previous_fps is None:
            seeded += len(current_rules)
        else:
            for rule_fp, (rule, host) in current_rules.items():
                if rule_fp in previous_fps or rule in local_rules or not publisher_id:
                    continue
                if suffix_match(host, SHARED_HOSTING_SUFFIXES):
                    rejected_shared += 1
                    continue
                entry = observations.setdefault(rule_fp, {
                    "rule": rule, "host": host, "category": "network",
                    "first_seen_utc": utc_now(), "last_seen_utc": utc_now(), "sources": []
                })
                entry["last_seen_utc"] = utc_now()
                source_id = fingerprint(name + "\0" + str(feed["url"]))[:16]
                if not any(x.get("id") == source_id for x in entry.get("sources", [])):
                    entry.setdefault("sources", []).append({
                        "id": source_id,
                        "name": name, "url": str(feed["url"]), "feed_host": feed_host,
                        "publisher_id": publisher_id,
                        "observed_at_utc": utc_now(),
                        "detail": "Exact rule newly appeared in a fresh or checksum-verified HTTP 304 feed snapshot. This is source-presence evidence, not proof of maliciousness or compatibility."
                    })
                entry["sources"] = entry.get("sources", [])[:8]
        updated_feeds[feed_key] = {
            "name": name, "url": str(feed["url"]), "feed_host": feed_host,
            "publisher_id": publisher_id,
            "sha256": state.get("sha256"), "validated_at_utc": state.get("last_confirmed_utc") or state.get("validated_at_utc"),
            "rule_fingerprints": sorted(current_rules),
        }

    # Keep the pending evidence window bounded and discard expired proposals.
    expired = []
    for rule_fp, entry in list(observations.items()):
        try:
            last_seen = parse_utc(str(entry.get("last_seen_utc", "")))
        except (ValueError, TypeError):
            expired.append(rule_fp)
            continue
        if last_seen < cutoff:
            expired.append(rule_fp)
    for rule_fp in expired:
        observations.pop(rule_fp, None)

    candidates = []
    held = []
    for rule_fp, entry in observations.items():
        rule = str(entry.get("rule", ""))
        if rule in local_rules:
            continue
        sources = entry.get("sources", [])
        unique_publishers = {str(x.get("publisher_id", "")) for x in sources if x.get("publisher_id")}
        reviewed_record = baseline["reviewed"].get(rule_fp)
        if isinstance(reviewed_record, dict) and set(reviewed_record.get("publisher_ids", [])) == unique_publishers:
            continue
        if len(unique_publishers) < min_publishers:
            held.append({"candidate_id": rule_fp[:16], "rule": rule, "publisher_count": len(unique_publishers),
                         "status": "held_insufficient_publisher_diversity"})
            continue
        evidence = [{"id": str(source["id"]), "source": str(source["name"]), "url": str(source["url"]),
                     "publisher_id": str(source["publisher_id"]),
                     "feed_host": str(source.get("feed_host", "")),
                     "detail": str(source["detail"]), "observed_at": str(source["observed_at_utc"])}
                    for source in sources if source.get("publisher_id")][:8]
        candidates.append({
            "id": rule_fp[:16], "rule": rule, "category": "network",
            "rationale": "Newly observed exact third-party host rule with publisher-diverse source observations. Treat as an untrusted candidate requiring source, semantics, false-positive, and compatibility review; do not assume maliciousness.",
            "evidence": evidence,
        })
    candidates.sort(key=lambda x: (-len(x["evidence"]), x["id"]))
    overflow = max(0, len(candidates) - max_candidates)
    selected = candidates[:max_candidates]
    project_version = Path("VERSION").read_text(encoding="utf-8").strip() if Path("VERSION").exists() else "unknown"
    bundle = {"schema_version": 1, "project_version": project_version,
              "review_id": f"discovery-{now.strftime('%Y%m%dT%H%M%SZ')}", "candidates": selected}

    # Baseline advances only for individually verified fresh/304 feeds. Failed
    # sources retain their previous state, and stale cache never contributes.
    updated_baseline = {"schema_version": 2, "updated_at_utc": utc_now(), "feeds": updated_feeds,
                        "observations": observations, "reviewed": baseline["reviewed"]}
    atomic_json(baseline_path, updated_baseline)
    atomic_json(output_path, bundle)
    report = {
        "schema_version": 2, "generated_at_utc": utc_now(), "mode": "read_only_delta_candidate_discovery",
        "successful_fresh_or_304_adblock_feeds": successful_feeds,
        "candidate_rule_lines_examined": examined, "baseline_seeded_rule_count": seeded,
        "newly_correlated_candidates": len(selected), "held_insufficient_publisher_diversity": len(held),
        "shared_hosting_candidates_skipped": rejected_shared, "expired_observations_removed": len(expired),
        "candidate_limit": max_candidates, "overflow_not_emitted": overflow,
        "minimum_distinct_publishers": min_publishers,
        "publisher_ids_are_curated_grouping_metadata_not_cryptographic_proof": True,
        "publisher_diversity_is_not_proof_of_editorial_independence": True,
        "candidate_rules_added_to_production": 0, "publication_authorized": False,
        "held_candidates_sample": held[:100], "source_errors": source_errors,
        "candidate_bundle": str(output_path),
        "notice": "Candidates are advisory only. Feed presence does not establish threat status, intent, safety, or browser compatibility. No source modules or production artifacts were changed."
    }
    return report


def mark_candidates_reviewed(baseline_path: Path, bundle_path: Path, swarm_report_path: Path) -> int:
    """Suppress repeat AI reviews only after a complete configured swarm pass."""
    baseline = load_baseline(baseline_path)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    report = json.loads(swarm_report_path.read_text(encoding="utf-8"))
    if not (report.get("mode") == "bounded_multi_agent_advisory_review" and
            report.get("ai_enabled") is True and
            report.get("synthesis", {}).get("swarm_complete") is True and
            not report.get("failures")):
        return 0
    reviewed = baseline["reviewed"]
    count = 0
    for candidate in bundle.get("candidates", []):
        fp = fingerprint(str(candidate.get("rule", "")))
        publisher_ids = sorted({str(item.get("publisher_id"))
                                 for item in candidate.get("evidence", []) if item.get("publisher_id")})
        reviewed[fp] = {"reviewed_at_utc": utc_now(), "review_id": str(bundle.get("review_id", "")),
                        "publisher_ids": publisher_ids}
        count += 1
    baseline["reviewed"] = reviewed
    atomic_json(baseline_path, baseline)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("config/reference_feeds.json"))
    parser.add_argument("--feed-report", type=Path, default=Path("reports/trihexomega-feed-cache-report.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("reports/trihexomega-feed-cache"))
    parser.add_argument("--modules", type=Path, default=Path("src/modules"))
    parser.add_argument("--baseline", type=Path, default=Path("reports/trihexomega-discovery-baseline.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/trihexomega-candidate-proposals.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/trihexomega-discovery-report.json"))
    parser.add_argument("--min-publishers", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--policy", type=Path, default=Path("config/trihexomega_policy.json"))
    parser.add_argument("--agents", type=Path, default=Path("config/trihexomega_agents.json"))
    args = parser.parse_args()
    from trihexomega.swarm import load_runtime_configuration
    runtime = load_runtime_configuration(args.agents, args.policy)
    if args.min_publishers < runtime["minimum_publisher_groups"]:
        raise ValueError("CLI publisher threshold cannot be lower than the validated policy")
    if args.max_candidates > runtime["max_candidates"]:
        raise ValueError("CLI candidate cap cannot exceed the validated policy")
    result = discover_candidates(args.registry, args.feed_report, args.cache_dir, args.modules,
                                 args.baseline, args.output, args.min_publishers, args.max_candidates,
                                 runtime["observation_days"])
    atomic_json(args.report, result)
    print(json.dumps({k: result[k] for k in ("successful_fresh_or_304_adblock_feeds", "newly_correlated_candidates",
                                               "held_insufficient_publisher_diversity", "candidate_rules_added_to_production",
                                               "publication_authorized")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
