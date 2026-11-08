#!/usr/bin/env python3
"""Validate TRIHEXΩ package structure, policy, configuration, and Python syntax."""
from __future__ import annotations
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
REQUIRED = (
    "VERSION", "Trihexoct.txt", "Trihexoct.meta.json", "config/reference_feeds.json",
    "config/trihexomega_agents.json", "config/trihexomega_policy.json",
    "tools/trihexomega/cache.py", "tools/trihexomega/swarm.py",
    "tools/trihexomega/candidate_discovery.py", "tools/trihexomega/policy_engine.py",
    "tools/trihexomega/source_health.py", "tools/trihexomega/orchestrator.py",
    "tools/trihexomega/change_impact.py", "tools/trihexomega/doctor.py",
    "tools/trihexomega/feedback_ledger.py", "tools/trihexomega/learning_engine.py", "tools/trihexomega/drift_guard.py",
    "tools/trihexomega/evolution_planner.py",
    ".github/workflows/main.yml", ".github/workflows/trihexomega-autonomous-cycle.yml",
    "tests/test_filter_project.py", "tests/test_trihexomega.py", "tests/test_trihexomega_advanced.py", "tests/test_trihexomega_alpha4.py", "tests/test_trihexomega_alpha5.py",
    "docs/TRIHEXOMEGA_RUNTIME_CONTRACT.md", "docs/EVOLUTION_PLANNER.md",
    "tests/test_trihexomega_evolution.py",
)
for relative in REQUIRED:
    if not (ROOT / relative).is_file():
        ERRORS.append(f"required project component missing: {relative}")
# Repository identity is intentionally separate from the original v1.3.2 repo.
EXPECTED_REPOSITORY = "368Guardlux/TrihexoctAI"
for workflow_name in ("main.yml", "trihexomega-advisory-review.yml", "trihexomega-autonomous-cycle.yml"):
    workflow_path = ROOT / ".github/workflows" / workflow_name
    if workflow_path.exists():
        workflow_text = workflow_path.read_text(encoding="utf-8")
        if EXPECTED_REPOSITORY not in workflow_text:
            ERRORS.append(f"{workflow_name} is not scoped to {EXPECTED_REPOSITORY}")
        if "github.repository == '368Guardlux/Trihexoct'" in workflow_text:
            ERRORS.append(f"{workflow_name} still targets the original v1.3.2 repository")

for relative in ("config/trihexomega_agents.json", "config/trihexomega_policy.json", "examples/candidate_proposals.example.json"):
    path = ROOT / relative
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        ERRORS.append(f"{relative}: {type(exc).__name__}: {exc}")
try:
    agents_config = json.loads((ROOT / "config/trihexomega_agents.json").read_text(encoding="utf-8"))
    agents = agents_config["agents"]
    if agents_config.get("schema_version") != 2 or len(agents) != 16 or len({x["id"] for x in agents}) != 16:
        ERRORS.append("agent registry must use schema 2 and contain sixteen unique role IDs")
    if sum(x.get("phase") == "analysis" for x in agents) != 12:
        ERRORS.append("agent registry must contain twelve analysis roles")
    if sum(x.get("phase") == "critique" for x in agents) != 3 or agents[-1].get("phase") != "synthesis":
        ERRORS.append("agent registry must contain three critique roles and end with synthesis")
    if agents_config.get("max_model_calls_per_run") != 16 or agents_config.get("max_parallel_agents") != 8:
        ERRORS.append("swarm call/concurrency budgets do not match the bounded design")
    if agents_config.get("max_candidates_per_run") != 8:
        ERRORS.append("candidate batch cap must be eight to keep per-review responses bounded")
except Exception as exc:
    ERRORS.append(f"agent registry check: {type(exc).__name__}: {exc}")
try:
    policy = json.loads((ROOT / "config/trihexomega_policy.json").read_text(encoding="utf-8"))
    for key in ("production_rule_edits_by_ai", "production_publication_by_ai", "ai_tool_execution", "ai_shell_access", "ai_repository_write_access", "ai_external_browsing", "ai_can_override_deterministic_gates"):
        if policy.get(key) is not False:
            ERRORS.append(f"safety policy must explicitly disable {key}")
    policy_caps = {
        "max_candidates_per_review": 8,
        "max_evidence_items_per_candidate": 8,
        "max_agent_calls_per_review": 16,
        "max_parallel_agents": 8,
        "max_agent_timeout_seconds": 45,
        "max_response_tokens_per_agent": 1400,
    }
    for key, expected in policy_caps.items():
        if policy.get(key) != expected:
            ERRORS.append(f"policy {key} must equal enforced runtime cap {expected}")
    impact = policy.get("release_impact", {})
    if impact.get("publication_authorized_by_impact_report") is not False or impact.get("require_human_review_for_any_candidate_change") is not True:
        ERRORS.append("change-impact policy must require human review and deny publication authority")
    if not 0.0 < float(impact.get("max_changed_rule_ratio_for_low_risk", 0)) <= 0.25:
        ERRORS.append("change-impact low-risk ratio must be within 0..25%")
    if policy.get("minimum_distinct_publisher_groups_for_discovery") != 2:
        ERRORS.append("policy must require two curated publisher groups for advisory candidate discovery")
    if policy.get("max_parallel_fetch_workers", 0) > 8 or policy.get("max_parallel_fetch_workers", 0) < 1:
        ERRORS.append("policy fetch-worker budget must be between 1 and 8")
    if policy.get("source_discovery", {}).get("production_rule_changes") != 0:
        ERRORS.append("candidate discovery must remain read-only")
    ai_runtime = policy.get("ai_runtime", {})
    for key, expected in {
        "maximum_model_calls_per_candidate_batch": 16,
        "maximum_parallel_analysis_calls": 8,
        "maximum_total_candidates": 8,
        "maximum_evidence_items_per_candidate": 8,
        "timeout_seconds": 45,
        "response_tokens_per_agent": 1400,
    }.items():
        if ai_runtime.get(key) != expected:
            ERRORS.append(f"AI runtime {key} must equal enforced cap {expected}")
    if ai_runtime.get("production_write_access") is not False or ai_runtime.get("agent_tool_use") is not False:
        ERRORS.append("AI runtime must not have production write or tool access")
    evolution = policy.get("evolution_planner", {})
    required_evolution_denials = ("may_modify_source_modules", "may_modify_filter_rules", "may_modify_policies_or_thresholds", "may_modify_source_identity_or_trust", "may_change_agent_permissions", "may_publish")
    if evolution.get("enabled") is not True or evolution.get("mode") != "deterministic_evidence_driven_backlog_only":
        ERRORS.append("evolution planner must be enabled in deterministic backlog-only mode")
    if any(evolution.get(key) is not False for key in required_evolution_denials):
        ERRORS.append("evolution planner must be denied all source, policy, trust, permission, and publication mutations")
    if evolution.get("maximum_recommendations") != 40 or evolution.get("maximum_state_tasks") != 5000 or evolution.get("maximum_state_bytes") != 2000000 or evolution.get("missing_task_auto_resolution") is not False:
        ERRORS.append("evolution planner recommendation, state, and non-resolution limits must match hard caps")
    if evolution.get("human_maintainer_decision_required") is not True:
        ERRORS.append("evolution planner must require human maintainer decisions")
    if not {"human_maintainer_approval", "stable_release_snapshot_exists", "candidate_has_compatibility_review"}.issubset(set(policy.get("release_requires", []))):
        ERRORS.append("policy release gates must require human approval, compatibility review, and a stable snapshot")
except Exception as exc:
    ERRORS.append(f"policy check: {type(exc).__name__}: {exc}")
try:
    registry = json.loads((ROOT / "config/reference_feeds.json").read_text(encoding="utf-8"))
    feeds = registry.get("feeds", [])
    if len(feeds) != 32:
        ERRORS.append(f"reference registry expected 32 configured feeds; found {len(feeds)}")
    for feed in feeds:
        publisher_id = feed.get("publisher_id")
        if not isinstance(publisher_id, str) or not publisher_id or not all(c.islower() or c.isdigit() or c in "._-" for c in publisher_id):
            ERRORS.append(f"feed {feed.get('name', '<unnamed>')} is missing a stable lowercase publisher_id")
except Exception as exc:
    ERRORS.append(f"reference registry publisher identity check: {type(exc).__name__}: {exc}")
try:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    meta = json.loads((ROOT / "Trihexoct.meta.json").read_text(encoding="utf-8"))
    if meta.get("project_version") != version:
        ERRORS.append("Trihexoct.meta.json version does not match VERSION")
    if f"! Version: {version}" not in (ROOT / "Trihexoct.txt").read_text(encoding="utf-8"):
        ERRORS.append("Trihexoct.txt version header does not match VERSION")
except Exception as exc:
    ERRORS.append(f"version consistency check: {type(exc).__name__}: {exc}")
for path in sorted((ROOT / "tools").rglob("*.py")):
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        ERRORS.append(str(exc))
try:
    main_workflow = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
    advisory_workflow = (ROOT / ".github/workflows/trihexomega-autonomous-cycle.yml").read_text(encoding="utf-8")
    if "trihexomega/doctor.py" not in main_workflow or "trihexomega/change_impact.py" not in main_workflow:
        ERRORS.append("main workflow must run doctor and change-impact diagnostics")
    if "trihexomega/doctor.py" not in advisory_workflow:
        ERRORS.append("autonomous workflow must run the network-free operations doctor")
    if "trihexomega-evolution-state.json" not in advisory_workflow or "trihexomega-evolution-plan.json" not in advisory_workflow:
        ERRORS.append("autonomous workflow must persist evolution state and upload the evolution plan")
    if "python tools/trihexomega/orchestrator.py" not in advisory_workflow:
        ERRORS.append("autonomous workflow must invoke the integrated read-only maintenance orchestrator")
    if "feedback_ledger.py verify" not in advisory_workflow:
        ERRORS.append("autonomous workflow must verify the human-feedback ledger before using learning diagnostics")
except OSError as exc:
    ERRORS.append(f"autonomous workflow integration check: {exc}")
if ERRORS:
    print("TRIHEXΩ package validation FAILED")
    print("\n".join(f"- {x}" for x in ERRORS), file=sys.stderr)
    raise SystemExit(1)
print("TRIHEXΩ package structure, 16-role staged swarm, supervised learning, drift guard, evolution planner, safety gates, version consistency, and Python syntax: PASS")
