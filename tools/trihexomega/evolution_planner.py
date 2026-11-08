#!/usr/bin/env python3
"""Build a deterministic, human-governed TRIHEXΩ improvement backlog.

This module turns operational reports into prioritized engineering actions.
It does not modify rules, policies, workflows, source identities, or releases.
Missing or malformed inputs are reported as unknown, never interpreted as
proof that a component is healthy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TOOLS_ROOT = str(Path(__file__).resolve().parents[1])
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

MAX_STATE_BYTES = 2_000_000
MAX_TASKS = 40
MAX_STATE_TASKS = 5000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "not_present"
    if path.stat().st_size > 5_000_000:
        return None, "oversized"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "invalid_shape"
    return value, None


def _task(task_key: str, title: str, priority: str, category: str, trigger: str,
          action: str, acceptance: list[str], recurrence: int = 0) -> dict[str, Any]:
    digest = hashlib.sha256(task_key.encode("utf-8")).hexdigest()[:20]
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}[priority]
    bounded_recurrence = max(0, min(int(recurrence), 100))
    return {
        "task_id": f"EVO-{digest}", "task_key": task_key, "title": title,
        "priority": priority, "priority_rank": rank, "category": category,
        "trigger": trigger[:700], "recommended_action": action[:1200],
        "acceptance_criteria": [str(x)[:300] for x in acceptance[:8]],
        "recurrence_count": bounded_recurrence,
        "recurrence_note": "Recurrence indicates repeated operational observation, not increased threat likelihood.",
        "owner_role": "maintainer", "status": "open",
        "requires_human_decision": True, "automatic_changes_authorized": False,
    }


def build_evolution_plan(reports_dir: Path, state_path: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate a bounded improvement plan and updated recurrence state."""
    reports_dir = Path(reports_dir)
    state_path = state_path or (reports_dir / "trihexomega-evolution-state.json")
    state: dict[str, Any] = {"schema_version": 1, "tasks": {}}
    if state_path.exists():
        if state_path.stat().st_size > MAX_STATE_BYTES:
            raise ValueError("evolution state exceeds 2 MB safety limit")
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("evolution state JSON is invalid; preserve it and inspect manually") from exc
        if not isinstance(loaded, dict) or loaded.get("schema_version") != 1 or not isinstance(loaded.get("tasks"), dict):
            raise ValueError("evolution state schema is invalid")
        state = loaded

    names = {
        "cycle": "trihexomega-cycle-report.json",
        "doctor": "trihexomega-doctor.json",
        "health": "trihexomega-source-health.json",
        "drift": "trihexomega-drift-report.json",
        "learning": "trihexomega-learning-report.json",
        "swarm": "trihexomega-swarm-review.json",
        "discovery": "trihexomega-discovery-report.json",
        "triage": "trihexomega-triage-report.json",
        "impact": "trihexomega-change-impact.json",
        "feed": "trihexomega-feed-cache-report.json",
    }
    inputs: dict[str, Any] = {}
    input_status: dict[str, str] = {}
    for key, filename in names.items():
        inputs[key], error = _read_json(reports_dir / filename)
        input_status[key] = "available" if error is None else error

    tasks: list[dict[str, Any]] = []
    cycle, doctor, health = inputs["cycle"], inputs["doctor"], inputs["health"]
    drift, learning, swarm = inputs["drift"], inputs["learning"], inputs["swarm"]
    discovery, triage, impact, feed = (inputs[k] for k in ("discovery", "triage", "impact", "feed"))

    if doctor is not None:
        failed = int(doctor.get("failed", doctor.get("summary", {}).get("failed", 0)) or 0)
        if failed > 0:
            tasks.append(_task("doctor-failures", "Resolve operations-doctor failures", "critical", "operations",
                f"Operations Doctor reports {failed} failed local checks.",
                "Inspect the doctor report and correct the underlying configuration or integrity issue before any release consideration.",
                ["Doctor reports zero failures", "Package and workflow validators pass"]))
    elif input_status["doctor"] != "not_present":
        tasks.append(_task("doctor-report-invalid", "Repair operations-doctor reporting", "high", "observability",
            f"Operations Doctor report is {input_status['doctor']}.",
            "Regenerate the report and verify that the diagnostic workflow completed. Do not infer health from a missing or invalid report.",
            ["A parseable doctor report exists", "The report contains explicit check results"]))

    if cycle is not None:
        gaps = cycle.get("required_group_gaps", {})
        if isinstance(gaps, dict) and gaps:
            tasks.append(_task("required-feed-groups", "Investigate required reference-feed group gaps", "high", "source_reliability",
                f"Required source groups are below configured minimums: {json.dumps(gaps, sort_keys=True)[:500]}.",
                "Inspect the affected feeds, source registry, and fetch diagnostics. Preserve current production rules while investigating.",
                ["Required source groups meet configured minimums", "Any unavailable feed has a documented cause"]))

    if feed is not None:
        configured = int(feed.get("feed_count", 0) or 0)
        good = int(feed.get("validated_fresh_or_304_count", 0) or 0)
        if configured and good < configured:
            tasks.append(_task("feed-availability", "Investigate incomplete reference-feed retrieval", "high", "source_reliability",
                f"{good} of {configured} configured feeds were validated fresh or via verified 304.",
                "Review per-feed errors, cache integrity, redirects, and source availability. Do not use stale cache as current coverage.",
                ["Per-feed outcomes are explained", "Required source groups recover or are explicitly held"]))

    if health is not None:
        degraded = int(health.get("degraded", 0) or 0)
        unreliable = int(health.get("unreliable", 0) or 0)
        if unreliable:
            tasks.append(_task("unreliable-sources", "Review repeatedly unreliable reference sources", "high", "source_reliability",
                f"Source-health diagnostics report {unreliable} unreliable source(s).",
                "Inspect source history and availability. Health status is diagnostic only; do not automatically remove or reweight a source.",
                ["Every unreliable source has a maintainer disposition", "Registry identity remains explicit"]))
        elif degraded:
            tasks.append(_task("degraded-sources", "Review degraded reference-source health", "medium", "source_reliability",
                f"Source-health diagnostics report {degraded} degraded source(s).",
                "Check whether transient errors are recurring and whether conditional cache validators are behaving correctly.",
                ["Degraded source trends are documented", "No stale data is credited as fresh coverage"]))

    if drift is not None:
        summary = drift.get("summary", {})
        held = int(summary.get("held_large_delta", 0) or 0)
        unavailable = int(summary.get("unavailable", 0) or 0)
        if held:
            tasks.append(_task("source-drift-review", "Review reference feeds held by the drift guard", "high", "source_integrity",
                f"The discovery-only drift guard held {held} feed(s) for unusual changes.",
                "Compare the feed change against its upstream release notes and prior snapshots. Rebaseline only through an explicit maintainer-reviewed process.",
                ["Each held feed has an investigated disposition", "No automatic rebaseline occurred"]))
        if unavailable:
            tasks.append(_task("drift-cache-verification", "Investigate unavailable drift snapshots", "medium", "source_integrity",
                f"{unavailable} feed(s) could not be evaluated against a matching verified cache snapshot.",
                "Inspect cache metadata, body checksum, and source report identity before using the snapshot for discovery.",
                ["Cache/report identity matches or feed remains held", "Production feed coverage is unchanged"]))

    if learning is not None:
        if learning.get("ledger_valid") is not True:
            tasks.append(_task("feedback-ledger-integrity", "Repair or quarantine the human-feedback ledger", "critical", "learning_integrity",
                "The feedback ledger does not report valid hash-chain integrity.",
                "Preserve a copy, inspect the first invalid event, and restore only from a trusted reviewed backup. Do not use invalid learning data.",
                ["Ledger hash chain verifies", "Invalid events are not silently discarded"]))
        else:
            for category, stats in (learning.get("categories", {}) or {}).items():
                if not isinstance(stats, dict):
                    continue
                negatives = int(stats.get("confirmed_negative", 0) or 0)
                if negatives:
                    tasks.append(_task(f"false-positive-review:{category}", f"Investigate historical negative outcomes in {category}", "high", "compatibility",
                        f"Human-adjudicated ledger records {negatives} negative outcome(s) for category {category}.",
                        "Review the exact candidate/evidence hashes and identify whether the issue arose from rule scope, evidence quality, or site functionality. Do not generalize one case to an entire category.",
                        ["Each negative outcome is classified", "Any proposed correction receives regression and compatibility tests"]))
                count = int(stats.get("confirmed_label_count", 0) or 0)
                minimum = int(learning.get("minimum_labels_for_diagnostic", 8) or 8)
                if 0 < count < minimum:
                    tasks.append(_task(f"feedback-sample:{category}", f"Collect more adjudicated outcomes for {category}", "low", "learning_quality",
                        f"Category {category} has {count} confirmed outcome(s), below the diagnostic minimum of {minimum}.",
                        "Continue recording real human outcomes after trials; do not treat provisional approvals or agent votes as ground truth.",
                        [f"At least {minimum} confirmed human outcomes are available before displaying a category diagnostic"]))

    if swarm is not None:
        if swarm.get("ai_enabled") and swarm.get("synthesis", {}).get("swarm_complete") is not True:
            tasks.append(_task("incomplete-swarm-review", "Investigate incomplete specialist review cycles", "high", "ai_reliability",
                "The latest model-assisted review did not complete every required stage.",
                "Inspect provider timeouts, malformed responses, schema errors, and rate limits. Missing reviews must continue to hold affected candidates.",
                ["All required roles complete or the candidate remains held", "Provider failures are visible and bounded"]))
        elif not swarm.get("ai_enabled") and discovery and int(discovery.get("newly_correlated_candidates", 0) or 0) > 0:
            tasks.append(_task("optional-ai-provider", "Decide whether to configure the optional AI review provider", "low", "ai_operations",
                "Candidate proposals exist but no model-assisted review is enabled.",
                "A maintainer may configure a vetted HTTPS model endpoint and review its data terms, latency, output limits, and cost. Deterministic pre-screening remains available without AI.",
                ["Provider configuration is explicit and secret-safe", "No provider is required for the deterministic maintenance cycle"]))

    if discovery is not None and triage is not None:
        count = int(discovery.get("newly_correlated_candidates", 0) or 0)
        if count and not triage.get("ranked_candidates"):
            tasks.append(_task("candidate-triage-gap", "Investigate candidates missing from adaptive triage", "medium", "discovery_quality",
                f"Discovery reports {count} candidate(s), but the triage report contains no ranked entries.",
                "Trace candidates through policy screening and verify that held items remain visible in diagnostics.",
                ["Every discovered candidate has an explicit eligible or held disposition"]))

    if impact is not None:
        high_risk = int(impact.get("high_risk_count", impact.get("summary", {}).get("high_risk_count", 0)) or 0)
        if high_risk:
            tasks.append(_task("high-impact-changes", "Investigate high-impact filter-list changes", "critical", "release_safety",
                f"Change-impact analysis reports {high_risk} high-risk change(s).",
                "Inspect exact changed lines and evidence. Keep the production list unchanged until human review and all release gates pass.",
                ["Every high-risk change has a reviewed disposition", "The stable artifact remains available"]))

    # Add recurrence information; absence in a new cycle never auto-closes a task.
    previous = state.get("tasks", {})
    now = utc_now()
    next_tasks: dict[str, Any] = {}
    for row in tasks:
        old = previous.get(row["task_id"], {}) if isinstance(previous, dict) else {}
        first_seen = old.get("first_seen_utc", now)
        recurrence = min(100, int(old.get("seen_cycles", 0) or 0) + 1)
        row["recurrence_count"] = recurrence
        row["first_seen_utc"] = first_seen
        row["last_seen_utc"] = now
        row["priority_rank"] = {"critical": 0, "high": 1, "medium": 2, "low": 3}[row["priority"]]
        next_tasks[row["task_id"]] = {"task_key": row["task_key"], "first_seen_utc": first_seen,
                                       "last_seen_utc": now, "seen_cycles": recurrence,
                                       "observed_this_cycle": True,
                                       "last_observation_state": "observed"}
    tasks.sort(key=lambda x: (x["priority_rank"], -x["recurrence_count"], x["task_id"]))
    tasks = tasks[:MAX_TASKS]
    # Retain historical observations. A task absent from the current cycle is
    # marked not_observed_this_cycle, never resolved or deleted automatically.
    retained_state = {}
    for task_id, old in previous.items():
        if task_id not in next_tasks and isinstance(old, dict):
            retained_state[task_id] = {**old, "observed_this_cycle": False,
                                      "last_observation_state": "not_observed_this_cycle"}
    retained_state.update(next_tasks)
    if len(retained_state) > MAX_STATE_TASKS:
        raise ValueError("evolution state exceeds 5,000 task-history entries; archive it with maintainer review")
    new_state = {"schema_version": 1, "updated_at_utc": now, "tasks": retained_state,
                 "state_contract": "Observation history only. Missing tasks are marked not_observed_this_cycle, never automatically resolved or deleted."}
    carried = len(retained_state) - len(next_tasks)
    report = {
        "schema_version": 1, "generated_at_utc": now,
        "mode": "deterministic_evolution_planning_advisory_only",
        "inputs": input_status,
        "recommendation_count": len(tasks),
        "historical_task_records_retained": carried,
        "recommendations": tasks,
        "priority_semantics": "Engineering attention order only; not threat probability, maliciousness, or publication authority.",
        "self_learning_semantics": "Human feedback and repeated operational observations improve review ordering and engineering backlog relevance only.",
        "automatic_code_changes": 0, "automatic_policy_changes": 0,
        "automatic_rule_changes": 0, "automatic_publication": False,
        "human_maintainer_decision_required": True,
        "notice": "This planner never edits source modules, policies, trust identities, release thresholds, or published rules. Missing data is not interpreted as healthy."
    }
    return report, new_state


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    try:
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--state", type=Path, default=Path("reports/trihexomega-evolution-state.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/trihexomega-evolution-plan.json"))
    args = parser.parse_args()
    try:
        report, state = build_evolution_plan(args.reports_dir, args.state)
        atomic_write_json(args.output, report)
        atomic_write_json(args.state, state)
        print(json.dumps({"recommendation_count": report["recommendation_count"],
                          "output": str(args.output), "automatic_changes": 0}, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
