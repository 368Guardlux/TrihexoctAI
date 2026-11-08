#!/usr/bin/env python3
"""Create a deterministic inventory of Trihexoct's reviewed source modules.

This audit is read-only: it inspects text, hashes files, checks the same policy
as the builder, and records duplicate/risk findings. It never fetches or executes
module content.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_filter import active, normalize_rule, validate_rule  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def category(rule: str) -> str:
    if '$removeparam=' in rule.lower(): return 'url_parameter'
    if '##' in rule: return 'cosmetic'
    if rule.startswith(('||', '|')): return 'network'
    if rule.startswith(('/', '*/')): return 'path_or_regex'
    return 'other'


def build_inventory() -> dict:
    modules = sorted((ROOT / 'src' / 'modules').glob('*.txt'))
    if not modules:
        raise RuntimeError('no source modules found')
    seen: dict[str, str] = {}
    duplicates = []
    rejected = []
    module_reports = []
    totals = {'active_rules': 0, 'network': 0, 'url_parameter': 0,
              'cosmetic': 0, 'path_or_regex': 0, 'other': 0}
    for path in modules:
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode('utf-8-sig', errors='strict')
        rules = [normalize_rule(line.strip()) for line in text.splitlines() if active(line)]
        counts = {k: 0 for k in ('network','url_parameter','cosmetic','path_or_regex','other')}
        for line_no, rule in enumerate(rules, 1):
            kind = category(rule); counts[kind] += 1
            issue = validate_rule(rule)
            if issue:
                rejected.append({'module': path.name, 'line': line_no, 'rule': rule, 'issue': issue})
            previous = seen.get(rule)
            if previous:
                duplicates.append({'rule': rule, 'first_module': previous, 'duplicate_module': path.name})
            else:
                seen[rule] = path.name
        active_count = len(rules)
        totals['active_rules'] += active_count
        for k, v in counts.items(): totals[k] += v
        module_reports.append({
            'module': path.name, 'bytes': len(raw_bytes), 'physical_lines': len(text.splitlines()),
            'active_rules': active_count, 'categories': counts, 'sha256': sha256(raw_bytes)
        })
    return {
        'schema_version': 1,
        'project_version': (ROOT / 'VERSION').read_text(encoding='utf-8').strip(),
        'source_module_count': len(module_reports),
        'totals': totals,
        'exact_duplicate_count': len(duplicates),
        'policy_violation_count': len(rejected),
        'modules': module_reports,
        'duplicates': duplicates,
        'policy_violations': rejected,
        'notes': [
            'Deterministic source inventory; no source code is executed.',
            'Counts describe authored module lines before online reference-feed reconciliation.',
            'Static policy checks do not replace parsing in Brave or live-site testing.'
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='optional JSON output path; stdout if omitted')
    parser.add_argument('--allow-duplicates', action='store_true', help='report but do not fail on duplicate active rules')
    args = parser.parse_args()
    try:
        result = build_inventory()
        encoded = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
        if args.output:
            out = args.output if args.output.is_absolute() else (ROOT / args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(encoded, encoding='utf-8', newline='\n')
        else:
            sys.stdout.write(encoded)
        print(f"AUDIT: {result['source_module_count']} modules; {result['totals']['active_rules']} source rules; "
              f"{result['exact_duplicate_count']} duplicates; {result['policy_violation_count']} policy violations", file=sys.stderr)
        if result['policy_violation_count']:
            return 1
        if result['exact_duplicate_count'] and not args.allow_duplicates:
            return 1
        return 0
    except (OSError, UnicodeDecodeError, RuntimeError, ValueError) as exc:
        print(f'ERROR: source inventory failed: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
