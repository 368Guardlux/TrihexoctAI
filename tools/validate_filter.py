#!/usr/bin/env python3
"""Static portability, manifest-integrity, and risk linter for Trihexoct."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_filter import validate_rule, active  # noqa: E402

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'Trihexoct.txt'
if not TARGET.is_absolute():
    TARGET = (ROOT / TARGET).resolve()
try:
    content = TARGET.read_bytes()
    lines = content.decode('utf-8-sig', errors='strict').splitlines()
except (OSError, UnicodeDecodeError) as exc:
    print(f'ERROR: cannot read valid UTF-8 text from {TARGET}: {exc}', file=sys.stderr)
    raise SystemExit(2)

rules = [line.strip() for line in lines if active(line)]
errors = []
if not any(line.startswith('! Title: TrihexoctAI') for line in lines[:10]):
    errors.append('missing title metadata')
if not any(line.startswith('! Version: ') for line in lines[:10]):
    errors.append('missing version metadata')
if not any(line.startswith('! Build mode: ') for line in lines[:16]):
    errors.append('missing explicit online/offline build-mode metadata')
if len(rules) != len(set(rules)):
    errors.append(f'{len(rules)-len(set(rules))} exact duplicate active rules')
counts = {
    'network': sum(line.startswith('||') for line in rules),
    'url_parameter': sum('$removeparam=' in line.lower() for line in rules),
    'cosmetic': sum('##' in line for line in rules),
    'path_or_regex': sum(line.startswith(('/', '*/')) for line in rules),
}
coverage_counts = dict(counts)
for index, rule in enumerate(lines, 1):
    if not active(rule):
        continue
    problem = validate_rule(rule)
    if problem:
        errors.append(f'line {index}: {problem}: {rule}')
    if rule.count('##') > 1:
        errors.append(f'line {index}: malformed multiple cosmetic separators')

# When linting the canonical generated output, also verify its stable manifest.
canonical = (ROOT / 'Trihexoct.txt').resolve()
manifest_path = ROOT / 'Trihexoct.meta.json'
if TARGET.resolve() == canonical:
    if not manifest_path.exists():
        errors.append('canonical output is missing Trihexoct.meta.json; rebuild the list')
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            actual_hash = hashlib.sha256(content).hexdigest()
            if manifest.get('output_sha256') != actual_hash:
                errors.append('manifest SHA-256 does not match Trihexoct.txt; rebuild the list')
            if manifest.get('active_rule_count') != len(rules):
                errors.append('manifest active_rule_count does not match Trihexoct.txt')
            if manifest.get('rule_categories') != counts:
                errors.append('manifest rule_categories does not match the published active rules')
            effective = manifest.get('effective_rule_categories')
            covered = manifest.get('covered_rule_categories')
            if not isinstance(effective, dict) or not isinstance(covered, dict):
                errors.append('manifest is missing effective_rule_categories or covered_rule_categories')
            else:
                expected_keys = set(counts)
                if set(effective) != expected_keys or set(covered) != expected_keys:
                    errors.append('manifest category keys do not match the current schema')
                elif any(not isinstance(effective[k], int) or not isinstance(covered[k], int) or covered[k] < 0 or effective[k] != counts[k] + covered[k] for k in expected_keys):
                    errors.append('manifest effective category counts must equal published plus proven-covered counts')
                elif manifest.get('build_mode') == 'offline-bootstrap' and (effective != counts or any(covered.values()) or manifest.get('reference_coverage_complete')):
                    errors.append('offline bootstrap must receive no reference-coverage credit')
                elif manifest.get('build_mode') == 'online-reconciliation' and not manifest.get('reference_coverage_complete'):
                    errors.append('online-reconciliation mode requires complete reference coverage')
                elif manifest.get('build_mode') not in {'offline-bootstrap', 'online-reconciliation', 'partial-online-reconciliation'}:
                    errors.append('manifest build_mode is not recognized')
                else:
                    coverage_counts = effective
            version_file = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
            if manifest.get('project_version') != version_file:
                errors.append('manifest version does not match VERSION file')
            module_dir = ROOT / 'src' / 'modules'
            actual_modules = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(module_dir.glob('*.txt'))}
            if manifest.get('source_module_sha256') != actual_modules:
                errors.append('manifest source-module hashes do not match current modules; rebuild the list')
            registry_hash = hashlib.sha256((ROOT / 'config' / 'reference_feeds.json').read_bytes()).hexdigest()
            if manifest.get('reference_registry_sha256') != registry_hash:
                errors.append('manifest reference-registry hash does not match current registry; rebuild the list')
            if manifest.get('source_module_count') != len(actual_modules):
                errors.append('manifest source-module count does not match current modules')
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f'manifest is unreadable or invalid: {exc}')

# On the published artifact, effective counts can include only rules removed on
# the strength of validated reference-feed evidence recorded in its manifest.
# For a temporary/non-canonical offline build, only the actual output counts.
for category, minimum in {'network': 200, 'url_parameter': 40, 'cosmetic': 20, 'path_or_regex': 5}.items():
    if coverage_counts.get(category, 0) < minimum:
        errors.append(f'{category} effective coverage too small: {coverage_counts.get(category, 0)} < {minimum}')

if errors:
    print('\n'.join('ERROR: ' + error for error in errors))
    raise SystemExit(1)
print(f'PASS: {TARGET.name}: {len(rules)} unique active rules; {len(lines)} total lines')
print('Published categories:', counts)
print('Effective categories used for floors:', coverage_counts)
print('PASS: static risk policy; no scriptlets/CSP/socket bans/credential removal/important overrides.')
if TARGET.resolve() == canonical:
    print('PASS: canonical output checksum, active-rule count, and version manifest match.')
print('LIMIT: static checks do not replace Brave engine parsing or live-site compatibility testing.')
