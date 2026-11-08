#!/usr/bin/env python3
"""Append-only human review memory; AI agents are never allowed to write it."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    from .swarm import validate_candidate_bundle, load_json
except ImportError:  # direct script execution from tools/trihexomega/
    from swarm import validate_candidate_bundle, load_json

VALID_DECISIONS = {"approved_for_beta", "rejected", "needs_more_evidence", "retired"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def candidate_fingerprint(candidate: dict[str, Any]) -> str:
    canonical = candidate["category"] + "\0" + candidate["rule"]
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_fingerprint(candidate: dict[str, Any]) -> str:
    records = sorted((item["id"] + "\0" + item["source"] + "\0" + item["url"] + "\0" + item["detail"])
                    for item in candidate["evidence"])
    return hashlib.sha256("\n".join(records).encode("utf-8")).hexdigest()


def record_decision(bundle_path: Path, candidate_id: str, decision: str, reason: str, memory_path: Path) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")
    if len(reason.strip()) > 500:
        raise ValueError("reason must be at most 500 characters")
    bundle = validate_candidate_bundle(load_json(bundle_path))
    candidate = next((x for x in bundle["candidates"] if x["id"] == candidate_id), None)
    if candidate is None:
        raise ValueError(f"candidate not found: {candidate_id}")
    row = {
        "schema_version": 1,
        "recorded_at_utc": utc_now(),
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_fingerprint(candidate),
        "evidence_sha256": evidence_fingerprint(candidate),
        "category": candidate["category"],
        "decision": decision,
        "reason": reason.strip(),
        "recorded_by": "human_maintainer",
    }
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    # O_APPEND reduces the chance of overwriting prior review history. This file
    # is maintainer-authored state, not model output.
    with memory_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
    return row


def lookup_memory(bundle_path: Path, memory_path: Path) -> dict[str, list[dict[str, Any]]]:
    bundle = validate_candidate_bundle(load_json(bundle_path))
    memory: dict[str, list[dict[str, Any]]] = {}
    if memory_path.exists():
        with memory_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError as exc:
                    raise ValueError(f"invalid memory JSON at line {line_number}") from exc
                if row.get("schema_version") != 1 or row.get("recorded_by") != "human_maintainer":
                    raise ValueError(f"invalid/untrusted memory record at line {line_number}")
                memory.setdefault(row.get("candidate_sha256", ""), []).append(row)
    output = {}
    for candidate in bundle["candidates"]:
        fingerprint = candidate_fingerprint(candidate)
        output[candidate["id"]] = memory.get(fingerprint, [])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--memory", type=Path, default=Path("reports/trihexomega-human-review-memory.jsonl"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", metavar="CANDIDATE_ID")
    group.add_argument("--lookup", action="store_true")
    parser.add_argument("--decision", choices=sorted(VALID_DECISIONS))
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    try:
        if args.record:
            if not args.decision:
                parser.error("--record requires --decision")
            row = record_decision(args.bundle, args.record, args.decision, args.reason, args.memory)
            print(json.dumps(row, indent=2))
        else:
            print(json.dumps(lookup_memory(args.bundle, args.memory), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
