#!/usr/bin/env python3
"""Read-only semantic change-impact analyzer for Trihexoct filter artifacts.

It compares two filter lists, classifies added/removed rules, flags broad-scope
changes, and emits a review recommendation. It never edits either list and
never authorizes publication. A report marked low-risk still requires the
project's independent gates and maintainer approval.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')


def active_rules(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8-sig', errors='strict')
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('!')]


def category(rule: str) -> str:
    low = rule.lower()
    if '$removeparam=' in low: return 'url_parameter'
    if '##' in rule or '#@#' in rule or '#?#' in rule: return 'cosmetic'
    if rule.startswith('||'): return 'network'
    if rule.startswith(('/', '*/')): return 'path_or_regex'
    return 'other'


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def inspect_added_rule(rule: str, policy: dict[str, Any]) -> list[str]:
    reasons=[]
    if category(rule) == 'network':
        head=rule.split('$',1)[0]
        if '*' in head and policy.get('hold_wildcard_domain_additions', True):
            reasons.append('wildcard network scope requires manual review')
        if '$third-party' not in rule.lower() and '$3p' not in rule.lower() and policy.get('hold_unscoped_network_additions', True):
            reasons.append('network addition is not explicitly third-party scoped')
        host=head[2:-1] if head.startswith('||') and head.endswith('^') else ''
        if not host or '.' not in host or len(host) > 253:
            reasons.append('network host scope is not a simple exact hostname')
    if category(rule) == 'cosmetic':
        left=rule.split('##',1)[0].split('#@#',1)[0].split('#?#',1)[0]
        if not left and policy.get('hold_global_cosmetic_additions', True):
            reasons.append('global cosmetic selector requires manual compatibility review')
        if any(x in rule.lower() for x in ('login','checkout','payment','consent','identity','accessibility')):
            reasons.append('selector text suggests a potentially essential interface; review required')
    if len(rule) > 500:
        reasons.append('unusually long rule requires manual inspection')
    return reasons


def analyze(baseline: Path, candidate: Path, policy_path: Path | None=None) -> dict[str, Any]:
    old=active_rules(baseline); new=active_rules(candidate)
    old_set=set(old); new_set=set(new)
    added=sorted(new_set-old_set); removed=sorted(old_set-new_set)
    duplicate_count=len(new)-len(new_set)
    policy=json.loads(policy_path.read_text(encoding='utf-8')) if policy_path else {}
    ratio=(len(added)+len(removed))/max(1,len(old_set))
    max_ratio=float(policy.get('max_changed_rule_ratio_for_low_risk',0.05))
    max_added=int(policy.get('max_added_rules_for_low_risk',20))
    max_removed=int(policy.get('max_removed_rules_for_low_risk',20))
    risky=[]
    for rule in added:
        reasons=inspect_added_rule(rule,policy)
        if reasons:
            risky.append({'rule':rule,'sha256':sha(rule),'reasons':reasons})
    blockers=[]
    if duplicate_count: blockers.append(f'candidate contains {duplicate_count} duplicate active rule lines')
    if ratio>max_ratio: blockers.append(f'changed-rule ratio {ratio:.2%} exceeds low-risk threshold {max_ratio:.2%}')
    if len(added)>max_added: blockers.append(f'{len(added)} added rules exceed low-risk threshold {max_added}')
    if len(removed)>max_removed: blockers.append(f'{len(removed)} removed rules exceed low-risk threshold {max_removed}')
    if risky: blockers.append(f'{len(risky)} added rules have broad-scope or essential-interface review flags')
    old_counts=Counter(category(x) for x in old_set); new_counts=Counter(category(x) for x in new_set)
    return {
      'schema_version':1,'generated_at_utc':utc_now(),'mode':'read_only_filter_change_impact',
      'baseline':{'path':str(baseline),'sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),'unique_rules':len(old_set)},
      'candidate':{'path':str(candidate),'sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'active_rule_lines':len(new),'unique_rules':len(new_set),'duplicate_lines':duplicate_count},
      'delta':{'added':len(added),'removed':len(removed),'changed_ratio':round(ratio,6),
               'added_by_category':dict(sorted(Counter(category(x) for x in added).items())),
               'removed_by_category':dict(sorted(Counter(category(x) for x in removed).items())),
               'baseline_by_category':dict(sorted(old_counts.items())),'candidate_by_category':dict(sorted(new_counts.items())),
               'added_rule_samples':[{'rule':x,'sha256':sha(x)} for x in added[:50]],
               'removed_rule_samples':[{'rule':x,'sha256':sha(x)} for x in removed[:50]]},
      'review_flags':risky[:100], 'blockers':blockers,
      'recommendation':'low_risk_for_independent_review' if not blockers else 'hold_for_manual_review',
      'human_review_required':True,'manual_review_override_used':False,'publication_authorized':False,
      'notice':'This is a deterministic change-impact heuristic, not a proof of safety, threat status, or compatibility. Low-risk does not mean auto-approved.'
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--policy',type=Path,default=Path('config/trihexomega_policy.json'))
    p.add_argument('--output',type=Path,default=Path('reports/trihexomega-change-impact.json'))
    p.add_argument('--strict',action='store_true',help='return exit 1 when manual review is required')
    p.add_argument('--accept-review',action='store_true',
                   help='record an explicit external manual-review override; does not authorize publication')
    a=p.parse_args()
    try:
      result=analyze(a.baseline,a.candidate,a.policy)
      result['manual_review_override_used']=a.accept_review
      if a.accept_review:
        result['manual_review_override_notice']='An external maintainer attested that the held change was reviewed; production approval is still required.'
      a.output.parent.mkdir(parents=True,exist_ok=True)
      tmp=a.output.with_name('.'+a.output.name+'.tmp')
      tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); tmp.replace(a.output)
      print(json.dumps({'recommendation':result['recommendation'],'added':result['delta']['added'],'removed':result['delta']['removed'],'review_flags':len(result['review_flags']),'manual_review_override_used':a.accept_review,'publication_authorized':False,'output':str(a.output)},indent=2))
      return 1 if a.strict and result['blockers'] and not a.accept_review else 0
    except (OSError,ValueError,json.JSONDecodeError) as exc:
      print(f'ERROR: {type(exc).__name__}: {exc}',file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
