#!/usr/bin/env python3
"""Deterministic pre-screen for automatically discovered filter candidates.

The policy engine is intentionally conservative. It can hold proposals; it
cannot create rules, edit source modules, or publish the production artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import re
from pathlib import Path

# Make direct `python tools/trihexomega/<module>.py` invocation work exactly
# like package execution and GitHub Actions commands. The package root is
# tools/, one directory above this module's folder.
_TOOLS_ROOT = str(Path(__file__).resolve().parents[1])
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)
from typing import Any
from urllib.parse import urlparse

from trihexomega.cache import atomic_json
from trihexomega.candidate_discovery import PROTECTED_SUFFIXES, SHARED_HOSTING_SUFFIXES, suffix_match
from trihexomega.swarm import validate_candidate_bundle

NETWORK_RULE = re.compile(r"^\|\|(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})\^\$third-party$", re.I)


def screen_candidate(candidate: dict[str, Any], min_publishers: int = 2) -> dict[str, Any]:
    if min_publishers < 2 or min_publishers > 8:
        raise ValueError("policy screening requires 2..8 curated publisher groups")
    rule = candidate["rule"].strip()
    reasons: list[str] = []
    match = NETWORK_RULE.fullmatch(rule)
    if candidate["category"] != "network":
        reasons.append("Only exact network host candidates are currently eligible for automated advisory screening.")
    if not match:
        reasons.append("Rule is not the narrow host-anchored third-party form; manual syntax and scope review is required.")
        host = ""
    else:
        host = match.group("host").lower().rstrip(".")
        protected = suffix_match(host, PROTECTED_SUFFIXES)
        shared = suffix_match(host, SHARED_HOSTING_SUFFIXES)
        if protected:
            reasons.append(f"Candidate matches protected functional infrastructure suffix: {protected}.")
        if shared:
            reasons.append(f"Candidate matches shared-hosting suffix: {shared}.")
    evidence = candidate.get("evidence", [])
    publishers = set()
    evidence_hosts = set()
    for item in evidence:
        parsed = urlparse(item["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            reasons.append("Evidence URL failed HTTPS identity validation.")
            continue
        evidence_hosts.add(parsed.hostname.lower().rstrip("."))
        publisher_id = str(item.get("publisher_id", "")).lower().strip()
        if publisher_id:
            publishers.add(publisher_id)
        else:
            reasons.append("Evidence is missing a registry-declared publisher ID.")
    if len(publishers) < min_publishers:
        reasons.append(f"Only {len(publishers)} distinct declared publishers; {min_publishers} required for advisory queueing.")
    # Publisher IDs are curated registry labels; they do not prove common
    # ownership, source independence, or correctness. They are better than
    # counting URLs hosted on the same platform, but remain a weak signal.
    return {"candidate_id": candidate["id"], "rule_sha256": hashlib.sha256(rule.encode("utf-8")).hexdigest(),
            "host": host or None, "decision": "eligible_for_advisory_review" if not reasons else "hold_for_manual_review",
            "reasons": reasons, "evidence_publisher_count": len(publishers),
            "evidence_hostname_count": len(evidence_hosts),
            "production_rule_changes": 0, "publication_authorized": False}


def screen_bundle(payload: dict[str, Any], min_publishers: int = 2) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = validate_candidate_bundle(payload)
    accepted, held = [], []
    decisions = []
    for candidate in bundle["candidates"]:
        verdict = screen_candidate(candidate, min_publishers)
        decisions.append(verdict)
        (accepted if verdict["decision"] == "eligible_for_advisory_review" else held).append(candidate)
    clean_bundle = {**bundle, "candidates": accepted}
    report = {"schema_version": 1, "mode": "deterministic_candidate_policy_screen",
              "candidate_count": len(bundle["candidates"]), "eligible_count": len(accepted),
              "held_count": len(held), "decisions": decisions,
              "production_rule_changes": 0, "publication_authorized": False,
              "notice": "Eligible means advisory review only. It is not an approval to add or publish a rule."}
    return clean_bundle, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("reports/trihexomega-candidate-proposals.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/trihexomega-candidate-proposals-screened.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/trihexomega-policy-screen.json"))
    parser.add_argument("--min-publishers", type=int, default=2)
    parser.add_argument("--policy", type=Path, default=Path("config/trihexomega_policy.json"))
    parser.add_argument("--agents", type=Path, default=Path("config/trihexomega_agents.json"))
    args = parser.parse_args()
    from trihexomega.swarm import load_runtime_configuration
    runtime = load_runtime_configuration(args.agents, args.policy)
    if args.min_publishers < runtime["minimum_publisher_groups"]:
        raise ValueError("CLI publisher threshold cannot be lower than the validated policy")
    bundle = json.loads(args.input.read_text(encoding="utf-8"))
    screened, report = screen_bundle(bundle, args.min_publishers)
    atomic_json(args.output, screened)
    atomic_json(args.report, report)
    print(json.dumps({k: report[k] for k in ("candidate_count", "eligible_count", "held_count", "publication_authorized")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
