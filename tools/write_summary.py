#!/usr/bin/env python3
"""Render a concise GitHub Actions summary from a Trihexoct build report."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def render(report: dict) -> str:
    lines = [
        "# Trihexoct build summary",
        f"- Project version: `{report.get('project_version', 'unknown')}`",
        f"- Published active rules: `{report.get('published_active_rules', 'not published')}`",
        f"- Reference feeds successful: `{report.get('successful_feed_count', 0)}/{report.get('total_feed_count', 0)}`",
        f"- Reference coverage complete: `{report.get('reference_coverage_complete', False)}`",
        f"- Removed as covered: `{report.get('removed_exact_and_covered_rules', 0)}`",
        f"- Published categories: `{report.get('published_rule_categories', {})}`",
        f"- Effective categories (published + proven covered): `{report.get('effective_rule_categories', {})}`",
        f"- Build aborted: `{report.get('build_aborted', False)}`",
    ]
    delta = report.get("output_delta") or {}
    if delta:
        lines.append(
            f"- Rule-set change: `{delta.get('changed_ratio', 'unknown')}` "
            f"(added `{delta.get('added_count', '?')}`, removed `{delta.get('removed_count', '?')}`)"
        )
        lines.append(f"- Output-delta gate passed: `{delta.get('gate_passed', 'not reported')}`")
    failures = report.get("failure_reasons") or []
    if failures:
        lines.append("\n## Failure reasons")
        lines.extend(f"- {reason}" for reason in failures)
    anomalies = report.get("feed_count_anomalies") or []
    if anomalies:
        lines.append("\n## Feed-count anomalies")
        for anomaly in anomalies:
            lines.append(
                f"- {anomaly.get('name', 'unknown')}: "
                f"{anomaly.get('previous_active_lines', '?')} → {anomaly.get('current_active_lines', '?')} "
                f"(ratio {anomaly.get('ratio', '?')})"
            )
    note = report.get("note")
    if note:
        lines.append(f"\n> {note}")
    return "\n".join(lines) + "\n"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/build-report.json")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("report root must be a JSON object")
        summary = render(report)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        summary = "# Trihexoct build summary\n\nBuild report unavailable or invalid. Inspect the workflow logs.\n"
        print(f"WARNING: {path}: {exc}", file=sys.stderr)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(summary)
    else:
        print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
