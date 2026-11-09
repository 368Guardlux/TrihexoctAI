#!/usr/bin/env python3
"""Build a deterministic source-module-to-rule provenance inventory."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def category(rule: str) -> str:
    low = rule.lower()
    if "$removeparam=" in low:
        return "url_parameter"
    if "##" in rule or "#@#" in rule or "#?#" in rule:
        return "cosmetic"
    if rule.startswith("||"):
        return "network"
    if rule.startswith(("/", "*/")):
        return "path_or_regex"
    return "other"


def build_inventory(module_dir: Path, project_version: str = "unknown") -> dict[str, Any]:
    paths = sorted(module_dir.glob("*.txt"), key=lambda p: p.name.casefold())
    if not paths:
        raise FileNotFoundError(f"no source modules found in {module_dir}")
    modules = []
    by_fingerprint: dict[str, list[dict[str, Any]]] = {}
    active_count = 0
    for path in paths:
        data = path.read_bytes()
        text = data.decode("utf-8-sig", errors="strict")
        records = []
        for line_number, raw in enumerate(text.splitlines(), 1):
            rule = raw.strip()
            if not rule or rule.startswith("!"):
                continue
            fingerprint = hashlib.sha256(rule.encode("utf-8")).hexdigest()
            item = {"module": path.name, "line": line_number, "category": category(rule),
                    "rule_sha256": fingerprint, "rule": rule}
            records.append(item)
            by_fingerprint.setdefault(fingerprint, []).append(item)
            active_count += 1
        modules.append({"name": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                        "active_rule_count": len(records)})
    duplicates = []
    for fingerprint, occurrences in sorted(by_fingerprint.items()):
        if len(occurrences) > 1:
            duplicates.append({"rule_sha256": fingerprint,
                               "locations": [{"module": x["module"], "line": x["line"]} for x in occurrences]})
    rules = [entries[0] for _, entries in sorted(by_fingerprint.items())]
    return {
        "schema_version": 1,
        "project_version": project_version,
        "generated_at_utc": utc_now(),
        "inventory_type": "source-module-rule-provenance",
        "module_count": len(modules),
        "source_active_line_count": active_count,
        "unique_rule_count": len(rules),
        "duplicate_rule_group_count": len(duplicates),
        "modules": modules,
        "rules": rules,
        "duplicate_groups": duplicates,
        "notice": "Provenance points to local source module lines. It does not establish threat status or browser compatibility.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modules", type=Path, default=Path("src/modules"))
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--output", type=Path, default=Path("reports/trihexomega-provenance.json"))
    args = parser.parse_args()
    try:
        version = args.version_file.read_text(encoding="utf-8").strip() if args.version_file.exists() else "unknown"
        result = build_inventory(args.modules, version)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_name("." + args.output.name + ".tmp")
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(args.output)
        summary = {k: result[k] for k in ("module_count", "source_active_line_count", "unique_rule_count", "duplicate_rule_group_count")}
        summary["output"] = str(args.output)
        print(json.dumps(summary, indent=2))
        return 0
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
