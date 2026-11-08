#!/usr/bin/env python3
"""Validate GitHub Actions workflow YAML and catch incomplete steps before CI runs."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
ALLOWED_ROOT_KEYS = {
    "name", "run-name", "on", "permissions", "env", "defaults",
    "concurrency", "jobs",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys instead of hiding them."""


def _construct_unique_mapping(loader: UniqueKeyLoader, node: MappingNode, deep: bool = False) -> dict:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError("while constructing a mapping", node.start_mark,
                                   "unhashable mapping key", key_node.start_mark) from exc
        if duplicate:
            raise ConstructorError("while constructing a mapping", node.start_mark,
                                   f"duplicate key {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def load_workflow(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read UTF-8 YAML: {exc}") from exc
    if "\t" in text:
        raise ValueError("tabs are not allowed in workflow YAML indentation")
    try:
        value = yaml.load(text, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("workflow root must be a YAML mapping")
    return value


def validate_workflow(path: Path) -> list[str]:
    label = str(path.relative_to(ROOT))
    problems: list[str] = []
    try:
        data = load_workflow(path)
    except ValueError as exc:
        return [f"{label}: {exc}"]

    unknown = sorted(set(data) - ALLOWED_ROOT_KEYS)
    if unknown:
        problems.append(f"{label}: unknown top-level key(s) {unknown}; Python/shell code must be inside a run: block")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        problems.append(f"{label}: missing non-empty workflow name")
    events = data.get("on")
    if not isinstance(events, dict) or not events:
        problems.append(f"{label}: missing quoted 'on' event mapping")
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        problems.append(f"{label}: jobs must be a non-empty mapping")
        return problems

    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            problems.append(f"{label}: job {job_id!r} must be a mapping")
            continue
        if not job.get("runs-on"):
            problems.append(f"{label}: job {job_id!r} is missing runs-on")
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"{label}: job {job_id!r} has no steps list")
            continue
        for index, step in enumerate(steps, 1):
            step_name = step.get("name", f"step {index}") if isinstance(step, dict) else f"step {index}"
            if not isinstance(step, dict):
                problems.append(f"{label}: job {job_id!r}, {step_name}: step must be a mapping")
                continue
            has_run = isinstance(step.get("run"), str) and bool(step["run"].strip())
            has_uses = isinstance(step.get("uses"), str) and bool(step["uses"].strip())
            if has_run == has_uses:
                problems.append(f"{label}: job {job_id!r}, {step_name}: step must contain exactly one non-empty run or uses field")
            if has_uses and "@" not in step["uses"]:
                problems.append(f"{label}: job {job_id!r}, {step_name}: action reference must include a version or SHA after @")

    if path.name == "main.yml":
        if not isinstance(events, dict) or not {"workflow_dispatch", "schedule", "push"}.issubset(events):
            problems.append(f"{label}: main build workflow must support workflow_dispatch, schedule, and push")
        build = jobs.get("build-and-validate")
        publisher = jobs.get("publish")
        if not isinstance(build, dict) or not isinstance(publisher, dict):
            problems.append(f"{label}: production workflow must separate build-and-validate and publish jobs")
        else:
            if not (isinstance(build.get("permissions"), dict) and build["permissions"].get("contents") == "read"):
                problems.append(f"{label}: build-and-validate job must have contents: read only")
            if not (isinstance(publisher.get("permissions"), dict) and publisher["permissions"].get("contents") == "write"):
                problems.append(f"{label}: only the separate publisher job may have contents: write")
            if publisher.get("needs") != "build-and-validate":
                problems.append(f"{label}: publisher must depend on successful build-and-validate job")
            build_steps = build.get("steps", [])
            checkout_steps = [s for s in build_steps if isinstance(s, dict) and s.get("uses", "").startswith("actions/checkout@")]
            if not checkout_steps or any((s.get("with") or {}).get("persist-credentials") is not False for s in checkout_steps):
                problems.append(f"{label}: read-only build checkout must disable persisted credentials")
            publisher_steps = publisher.get("steps", [])
            uses = [s.get("uses", "") for s in publisher_steps if isinstance(s, dict)]
            if not any(x.startswith("actions/download-artifact@") for x in uses):
                problems.append(f"{label}: publisher must download the validated build artifact")
            publisher_runs = "\n".join(s.get("run", "") for s in publisher_steps if isinstance(s, dict))
            if "sha256sum --check" not in publisher_runs:
                problems.append(f"{label}: publisher must verify the payload checksum before committing")
    return problems


def validate_all_workflows() -> list[str]:
    if not WORKFLOW_DIR.is_dir():
        return ["missing .github/workflows directory"]
    files = sorted(p for p in WORKFLOW_DIR.glob("*.yml") if p.is_file())
    files += sorted(p for p in WORKFLOW_DIR.glob("*.yaml") if p.is_file())
    if not files:
        return ["no .yml/.yaml workflow files found in .github/workflows"]
    return [problem for path in files for problem in validate_workflow(path)]


def main() -> int:
    problems = validate_all_workflows()
    if problems:
        print("WORKFLOW VALIDATION FAILED")
        for problem in problems:
            print(f"ERROR: {problem}")
        return 1
    count = len(list(WORKFLOW_DIR.glob("*.yml"))) + len(list(WORKFLOW_DIR.glob("*.yaml")))
    print(f"PASS: {count} GitHub Actions workflow file(s) parsed; all jobs and steps have valid structure.")
    print("LIMIT: this is a local structural check; GitHub Actions remains the final workflow execution test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
