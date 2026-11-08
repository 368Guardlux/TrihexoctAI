#!/usr/bin/env python3
"""Run one bounded TRIHEXΩ maintenance + discovery + advisory cycle.

This orchestrator never builds, edits, commits, or publishes the public filter
list. It fetches approved reference feeds, evaluates source health, discovers
conservative rule candidates from verified feed deltas, optionally runs the
read-only specialist swarm, and writes an auditable cycle report.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make direct `python tools/trihexomega/<module>.py` invocation work exactly
# like package execution and GitHub Actions commands. The package root is
# tools/, one directory above this module's folder.
_TOOLS_ROOT = str(Path(__file__).resolve().parents[1])
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)
from typing import Any

from trihexomega.cache import atomic_json, run_registry, validate_registry_config
from trihexomega.candidate_discovery import discover_candidates, mark_candidates_reviewed
from trihexomega.source_health import evaluate_health
from trihexomega.drift_guard import evaluate_drift
from trihexomega.feedback_ledger import build_learning_report
from trihexomega.learning_engine import rank_candidate_bundle
from trihexomega.evolution_planner import build_evolution_plan, atomic_write_json as write_evolution_json
from trihexomega.policy_engine import screen_bundle
from trihexomega.swarm import load_runtime_configuration, run_swarm


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def required_group_gaps(registry: dict[str, Any], feed_report: dict[str, Any]) -> dict[str, dict[str, int]]:
    feeds = validate_registry_config(registry)
    rows = {str(x.get("name")): x for x in feed_report.get("feeds", [])}
    gaps: dict[str, dict[str, int]] = {}
    for group, minimum in registry.get("required_groups", {}).items():
        healthy = sum(1 for feed in feeds if group in feed.get("groups", []) and
                      rows.get(str(feed["name"]), {}).get("ok") and
                      rows.get(str(feed["name"]), {}).get("coverage_eligible"))
        if healthy < int(minimum):
            gaps[group] = {"required": int(minimum), "available": healthy}
    return gaps


def run_cycle(registry_path: Path, cache_dir: Path, reports_dir: Path, modules_dir: Path,
              agents_path: Path, policy_path: Path, workers: int = 8, skip_ai: bool = False) -> dict[str, Any]:
    runtime = load_runtime_configuration(agents_path, policy_path)
    min_publishers = runtime["minimum_publisher_groups"]
    max_candidates = runtime["max_candidates"]
    workers = max(1, min(int(workers), runtime["max_fetch_workers"]))
    started = time.monotonic()
    reports_dir.mkdir(parents=True, exist_ok=True)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    stage_times: dict[str, float] = {}
    stages: dict[str, Any] = {}

    t = time.monotonic()
    feed_report_path = reports_dir / "trihexomega-feed-cache-report.json"
    controller_path = reports_dir / "trihexomega-cache-controller.json"
    feed_report = run_registry(registry_path, cache_dir, feed_report_path, workers, controller_path)
    stage_times["feed_sync_seconds"] = round(time.monotonic() - t, 3)
    stages["feed_sync"] = {"status": "completed", "successful": feed_report.get("validated_fresh_or_304_count", 0),
                            "configured": feed_report.get("feed_count", 0), "workers": feed_report.get("selected_workers")}

    t = time.monotonic()
    health_history_path = reports_dir / "trihexomega-source-health-history.json"
    previous_health = json.loads(health_history_path.read_text(encoding="utf-8")) if health_history_path.exists() else None
    health, updated_history = evaluate_health(feed_report, registry, previous_health)
    atomic_json(reports_dir / "trihexomega-source-health.json", health)
    atomic_json(health_history_path, updated_history)
    stage_times["source_health_seconds"] = round(time.monotonic() - t, 3)
    stages["source_health"] = {"status": "completed", "healthy_or_warming": health["healthy_or_warming"],
                               "degraded": health["degraded"], "unreliable": health["unreliable"]}

    t = time.monotonic()
    discovery_baseline_path = reports_dir / "trihexomega-discovery-baseline.json"
    discovery_baseline = (json.loads(discovery_baseline_path.read_text(encoding="utf-8"))
                          if discovery_baseline_path.exists()
                          else {"schema_version": 2, "feeds": {}, "observations": {}, "reviewed": {}})
    drift_filtered_report, drift_report = evaluate_drift(
        registry, feed_report, cache_dir, discovery_baseline,
        json.loads(policy_path.read_text(encoding="utf-8")),
    )
    drift_feed_report_path = reports_dir / "trihexomega-drift-screened-feed-report.json"
    drift_report_path = reports_dir / "trihexomega-drift-report.json"
    atomic_json(drift_feed_report_path, drift_filtered_report)
    atomic_json(drift_report_path, drift_report)
    stage_times["drift_guard_seconds"] = round(time.monotonic() - t, 3)
    stages["drift_guard"] = {"status": "completed", **drift_report["summary"],
                             "held_feed_count": len(drift_report["excluded_feed_names"]),
                             "production_coverage_modified": False}

    t = time.monotonic()
    proposal_path = reports_dir / "trihexomega-candidate-proposals.json"
    discovery_report = discover_candidates(
        registry_path, drift_feed_report_path, cache_dir, modules_dir,
        discovery_baseline_path, proposal_path,
        min_publishers=min_publishers, max_candidates=max_candidates,
        observation_days=runtime["observation_days"],
    )
    atomic_json(reports_dir / "trihexomega-discovery-report.json", discovery_report)
    stage_times["candidate_discovery_seconds"] = round(time.monotonic() - t, 3)
    stages["candidate_discovery"] = {"status": "completed", "candidates": discovery_report["newly_correlated_candidates"],
                                     "held": discovery_report["held_insufficient_publisher_diversity"],
                                     "production_rules_added": 0}

    t = time.monotonic()
    discovered_bundle = json.loads(proposal_path.read_text(encoding="utf-8"))
    bundle, policy_screen = screen_bundle(discovered_bundle, min_publishers=min_publishers)
    screened_path = reports_dir / "trihexomega-candidate-proposals-screened.json"
    policy_report_path = reports_dir / "trihexomega-policy-screen.json"
    atomic_json(screened_path, bundle)
    atomic_json(policy_report_path, policy_screen)
    stages["policy_screen"] = {"status": "completed", "eligible": policy_screen["eligible_count"],
                               "held": policy_screen["held_count"], "publication_authorized": False}
    # Build a tamper-evident human-feedback calibration report. This can alter
    # review ordering only; the raw ledger and reviewer rationale are never sent
    # to the model provider.
    learning_report_path = reports_dir / "trihexomega-learning-report.json"
    feedback_ledger_path = reports_dir / "trihexomega-review-feedback.jsonl"
    learning_report = build_learning_report(feedback_ledger_path)
    atomic_json(learning_report_path, learning_report)
    ranked_bundle, triage_report = rank_candidate_bundle(bundle, learning_report)
    atomic_json(reports_dir / "trihexomega-candidate-proposals-ranked.json", ranked_bundle)
    atomic_json(reports_dir / "trihexomega-triage-report.json", triage_report)
    bundle = ranked_bundle
    stages["human_feedback_learning"] = {"status": "completed", "verified_events": learning_report["ledger_event_count"],
                                          "confirmed_labels": learning_report["confirmed_positive_count"] + learning_report["confirmed_negative_count"],
                                          "policy_mutation": False}
    stages["adaptive_triage"] = {"status": "completed", "candidates_ranked": triage_report["candidate_count"],
                                 "changes_review_order_only": True, "production_rule_changes": 0}

    t = time.monotonic()
    swarm_report_path = reports_dir / "trihexomega-swarm-review.json"
    if skip_ai:
        # Empty/disabled AI mode is explicit and deterministic. The swarm's
        # own no-provider behavior produces a preflight report, never a release.
        import os
        old_key, old_model = os.environ.get("TRIHEXOMEGA_AI_API_KEY"), os.environ.get("TRIHEXOMEGA_AI_MODEL")
        os.environ["TRIHEXOMEGA_AI_API_KEY"] = ""
        os.environ["TRIHEXOMEGA_AI_MODEL"] = ""
        try:
            swarm_report = run_swarm(bundle, agents_path, max_workers=runtime["max_parallel_agents"],
                                     memory_path=reports_dir / "trihexomega-human-review-memory.jsonl",
                                     policy_path=policy_path, learning_context=learning_report)
        finally:
            if old_key is None: os.environ.pop("TRIHEXOMEGA_AI_API_KEY", None)
            else: os.environ["TRIHEXOMEGA_AI_API_KEY"] = old_key
            if old_model is None: os.environ.pop("TRIHEXOMEGA_AI_MODEL", None)
            else: os.environ["TRIHEXOMEGA_AI_MODEL"] = old_model
    else:
        swarm_report = run_swarm(bundle, agents_path, max_workers=runtime["max_parallel_agents"],
                                 memory_path=reports_dir / "trihexomega-human-review-memory.jsonl",
                                 policy_path=policy_path, learning_context=learning_report)
    atomic_json(swarm_report_path, swarm_report)
    reviewed_count = mark_candidates_reviewed(reports_dir / "trihexomega-discovery-baseline.json",
                                               screened_path, swarm_report_path)
    stage_times["swarm_seconds"] = round(time.monotonic() - t, 3)
    stages["cognitive_swarm"] = {"status": "completed" if not swarm_report.get("failures") else "degraded",
                                 "mode": swarm_report.get("mode"), "ai_enabled": swarm_report.get("ai_enabled"),
                                 "configured_specialists": swarm_report.get("agent_count_configured"),
                                 "calls_attempted": swarm_report.get("agent_calls_made", 0),
                                 "calls_succeeded": swarm_report.get("agent_calls_succeeded", 0),
                                 "calls_failed": swarm_report.get("agent_calls_failed", 0),
                                 "calls_skipped": swarm_report.get("agent_calls_skipped", 0),
                                 "complete": swarm_report.get("synthesis", {}).get("swarm_complete", False),
                                 "reviewed_candidates_suppressed": reviewed_count,
                                 "publication_authorized": False}

    gaps = required_group_gaps(registry, feed_report)
    total = time.monotonic() - started
    status = "completed" if not gaps else "degraded_required_source_coverage"
    cycle = {
        "schema_version": 1, "generated_at_utc": utc_now(),
        "project_version": Path("VERSION").read_text(encoding="utf-8").strip() if Path("VERSION").exists() else "unknown",
        "cycle_id": f"trihexomega-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "mode": "read_only_autonomous_maintenance_and_advisory_cycle",
        "status": status, "duration_seconds": round(total, 3), "stage_durations_seconds": stage_times,
        "stages": stages, "required_group_gaps": gaps,
        "source_count": feed_report.get("feed_count", 0),
        "validated_fresh_or_304_count": feed_report.get("validated_fresh_or_304_count", 0),
        "discovered_candidate_count": len(discovered_bundle.get("candidates", [])),
        "candidate_count": len(bundle.get("candidates", [])),
        "held_candidate_count": policy_screen["held_count"],
        "drift_held_feed_count": len(drift_report["excluded_feed_names"]),
        "human_feedback_events": learning_report["ledger_event_count"],
        "production_rule_changes": 0, "production_artifact_changes": 0,
        "commit_performed": False, "publication_authorized": False,
        "privacy": "Only public feed metadata and candidate rule strings are processed; no subscriber browsing data is collected.",
        "notice": "This cycle maintains caches, source-drift diagnostics, human-feedback learning diagnostics, and advisory reports only. It does not alter source modules, rebuild the public list, commit, or publish."
    }
    cycle_report_path = reports_dir / "trihexomega-cycle-report.json"
    atomic_json(cycle_report_path, cycle)

    # Deterministic evolution planning turns operational evidence into a
    # human-governed engineering backlog. It is read-only with respect to
    # filter rules, policy, source identity, and production releases.
    evolution_started = time.monotonic()
    evolution_plan, evolution_state = build_evolution_plan(
        reports_dir, reports_dir / "trihexomega-evolution-state.json"
    )
    evolution_duration = round(time.monotonic() - evolution_started, 3)
    write_evolution_json(reports_dir / "trihexomega-evolution-plan.json", evolution_plan)
    write_evolution_json(reports_dir / "trihexomega-evolution-state.json", evolution_state)
    cycle["stage_durations_seconds"]["evolution_planning_seconds"] = evolution_duration
    cycle["duration_seconds"] = round(float(cycle["duration_seconds"]) + evolution_duration, 3)
    cycle["stages"]["evolution_planner"] = {
        "status": "completed",
        "recommendations": evolution_plan["recommendation_count"],
        "historical_task_records_retained": evolution_plan.get("historical_task_records_retained", 0),
        "automatic_code_changes": 0,
        "automatic_policy_changes": 0,
        "automatic_rule_changes": 0,
        "publication_authorized": False,
    }
    cycle["evolution_planner"] = {
        "status": "completed",
        "recommendations": evolution_plan["recommendation_count"],
        "automatic_code_changes": 0,
        "automatic_policy_changes": 0,
        "automatic_rule_changes": 0,
        "publication_authorized": False,
    }
    atomic_json(cycle_report_path, cycle)
    return cycle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("config/reference_feeds.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path("reports/trihexomega-feed-cache"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--modules", type=Path, default=Path("src/modules"))
    parser.add_argument("--agents", type=Path, default=Path("config/trihexomega_agents.json"))
    parser.add_argument("--policy", type=Path, default=Path("config/trihexomega_policy.json"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-ai", action="store_true")
    args = parser.parse_args()
    try:
        report = run_cycle(args.registry, args.cache_dir, args.reports_dir, args.modules,
                           args.agents, args.policy, args.workers, args.skip_ai)
    except Exception as exc:
        print(f"TRIHEXΩ cycle failed safely: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps({k: report[k] for k in ("status", "duration_seconds", "source_count",
                                             "validated_fresh_or_304_count", "candidate_count",
                                             "production_rule_changes", "publication_authorized")}, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
