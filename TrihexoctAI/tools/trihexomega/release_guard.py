#!/usr/bin/env python3
"""Read-only release readiness evaluator for Trihexoct candidate artifacts.

This tool never publishes or commits. It checks explicit validation evidence,
artifact integrity, duplicate active rules, output delta, and swarm status.
The existing build_filter.py and validate_filter.py remain authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def active_rules(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("!")]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(candidate: Path, stable: Path, evidence_path: Path, swarm_path: Path,
             max_delta_ratio: float = 0.40) -> dict[str, Any]:
    blockers: list[str] = []
    checks: dict[str, bool] = {}
    if not candidate.is_file():
        raise FileNotFoundError(f"candidate artifact does not exist: {candidate}")
    if not stable.is_file():
        blockers.append("No stable reference artifact exists; establish a known-good baseline first.")
        old: list[str] = []
    else:
        old = active_rules(stable)
    new = active_rules(candidate)
    duplicates = len(new) - len(set(new))
    checks["candidate_utf8_readable"] = True
    checks["no_exact_duplicate_active_rules"] = duplicates == 0
    if duplicates:
        blockers.append(f"Candidate contains {duplicates} duplicate active rule lines.")
    checks["candidate_nonempty"] = bool(new)
    if not new:
        blockers.append("Candidate contains no active rules.")
    old_set, new_set = set(old), set(new)
    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    delta_ratio = (len(added) + len(removed)) / max(1, len(old_set))
    checks["output_delta_within_policy"] = delta_ratio <= max_delta_ratio
    if delta_ratio > max_delta_ratio:
        blockers.append(f"Output delta {delta_ratio:.1%} exceeds configured limit {max_delta_ratio:.1%}; manual investigation is required.")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else {}
    required_checks = ["regression_tests", "filter_validator", "source_audit", "compatibility_tests"]
    for name in required_checks:
        passed = evidence.get(name) == "passed"
        checks[f"{name}_passed"] = passed
        if not passed:
            blockers.append(f"Required validation evidence is absent or not passed: {name}.")
    human_approved = evidence.get("human_approval") is True
    checks["human_approval_recorded"] = human_approved
    if not human_approved:
        blockers.append("Explicit maintainer approval is not recorded.")
    swarm = json.loads(swarm_path.read_text(encoding="utf-8")) if swarm_path.exists() else {}
    swarm_failed = bool(swarm.get("failures"))
    swarm_complete = swarm.get("mode") == "no_candidates_to_review" or (swarm.get("ai_enabled") is True and swarm.get("synthesis", {}).get("swarm_complete") is True)
    checks["swarm_review_complete_or_not_required"] = bool(swarm_complete and not swarm_failed)
    if not checks["swarm_review_complete_or_not_required"]:
        blockers.append("Swarm review is missing, incomplete, or failed; keep all proposed changes on hold.")
    checks["swarm_cannot_authorize_publication"] = swarm.get("publication_authorized") is False
    if not checks["swarm_cannot_authorize_publication"]:
        blockers.append("Swarm report violates policy: publication_authorized must be false.")
    eligible = not blockers and all(checks.values())
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "mode": "read_only_release_readiness_evaluation",
        "candidate_sha256": digest(candidate),
        "stable_sha256": digest(stable) if stable.exists() else None,
        "stable_active_rules": len(old_set),
        "candidate_active_rules": len(new),
        "added_rules": len(added),
        "removed_rules": len(removed),
        "output_delta_ratio": round(delta_ratio, 6),
        "checks": checks,
        "blockers": blockers,
        "release_eligible_for_separate_publisher": eligible,
        "publication_authorized": False,
        "notice": "This evaluator never publishes, commits, or changes the production subscription. The existing publisher and maintainer remain authoritative."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("Trihexoct.txt"))
    parser.add_argument("--stable", type=Path, default=Path("reports/last-known-good/Trihexoct.txt"))
    parser.add_argument("--evidence", type=Path, default=Path("reports/trihexomega-validation-evidence.json"))
    parser.add_argument("--swarm", type=Path, default=Path("reports/trihexomega-swarm-review.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/trihexomega-release-readiness.json"))
    parser.add_argument("--max-delta-ratio", type=float, default=0.40)
    args = parser.parse_args()
    if not 0.0 <= args.max_delta_ratio <= 1.0:
        parser.error("--max-delta-ratio must be between 0 and 1")
    try:
        report = evaluate(args.candidate, args.stable, args.evidence, args.swarm, args.max_delta_ratio)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.output.with_name("." + args.output.name + ".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(args.output)
        print(json.dumps({"release_eligible_for_separate_publisher": report["release_eligible_for_separate_publisher"],
                          "publication_authorized": False, "blockers": report["blockers"], "output": str(args.output)}, indent=2))
        return 0 if report["release_eligible_for_separate_publisher"] else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
