#!/usr/bin/env python3
"""Per-feed drift guard for discovery, separate from production coverage.

Large unexpected rule-set changes are held out of candidate discovery. They
remain visible in diagnostics and do not remove a feed from the production
builder's independently validated reference coverage.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re, sys
from pathlib import Path
from typing import Any
from trihexomega.cache import load_cache, validate_bytes, atomic_json
from trihexomega.candidate_discovery import classify_rule, fingerprint

class DriftError(ValueError): pass

def feed_key(name:str,url:str)->str:
    return hashlib.sha256((name+"\0"+url).encode("utf-8")).hexdigest()

def evaluate_drift(registry:dict[str,Any], feed_report:dict[str,Any], cache_dir:Path,
                   discovery_baseline:dict[str,Any], policy:dict[str,Any])->tuple[dict[str,Any],dict[str,Any]]:
    cfg=policy.get("drift_guard",{})
    max_ratio=float(cfg.get("max_symmetric_delta_ratio",0.35)); min_changes=int(cfg.get("minimum_changed_rules",50))
    min_baseline=int(cfg.get("minimum_baseline_rules",80)); max_added=int(cfg.get("maximum_added_rules",500)); max_removed=int(cfg.get("maximum_removed_rules",500))
    if not (0.10<=max_ratio<=0.60 and 10<=min_changes<=500 and 20<=min_baseline<=1000 and 50<=max_added<=2000 and 50<=max_removed<=2000):
        raise DriftError("drift guard thresholds fall outside enforced hard bounds")
    if not isinstance(discovery_baseline,dict) or discovery_baseline.get("schema_version")!=2 or not isinstance(discovery_baseline.get("feeds"),dict):
        raise DriftError("discovery baseline is missing or invalid; run baseline initialization before drift screening")
    report_rows={str(x.get("name")):x for x in feed_report.get("feeds",[]) if isinstance(x,dict)}
    rows=[]; excluded=set(); summary={"baseline_seeded":0,"stable":0,"held_large_delta":0,"unavailable":0,"not_applicable":0}
    for feed in registry.get("feeds",[]):
        name=str(feed.get("name","")); url=str(feed.get("url","")); row=report_rows.get(name,{})
        if feed.get("format")!="adblock": summary["not_applicable"]+=1; continue
        if not row.get("ok") or not row.get("coverage_eligible"):
            summary["unavailable"]+=1; continue
        body,state=load_cache(cache_dir,name,url)
        if body is None or state is None or state.get("sha256")!=row.get("sha256"):
            excluded.add(name); rows.append({"feed":name,"status":"held_cache_mismatch","reason":"No matching verified cached body."}); summary["unavailable"]+=1; continue
        try: text,_=validate_bytes(body,feed)
        except Exception as exc:
            excluded.add(name); rows.append({"feed":name,"status":"held_cache_invalid","reason":type(exc).__name__}); summary["unavailable"]+=1; continue
        current={fingerprint(line.strip()) for line in text.splitlines() if classify_rule(line.strip())}
        previous=discovery_baseline["feeds"].get(feed_key(name,url))
        if not isinstance(previous,dict) or not isinstance(previous.get("rule_fingerprints"),list):
            summary["baseline_seeded"]+=1; rows.append({"feed":name,"status":"warming_baseline","current_rule_count":len(current)}); continue
        prior=set(str(x) for x in previous["rule_fingerprints"] if re.fullmatch(r"[a-f0-9]{64}",str(x)))
        added=current-prior; removed=prior-current; changed=len(added)+len(removed); union=len(current|prior)
        ratio=changed/max(1,union); base=len(prior)
        reasons=[]
        if base>=min_baseline and changed>=min_changes and ratio>=max_ratio:
            reasons.append("symmetric rule-set delta exceeds configured ratio and minimum-change thresholds")
        if len(added)>=max_added: reasons.append("absolute additions exceed configured cap")
        if len(removed)>=max_removed: reasons.append("absolute removals exceed configured cap")
        held=bool(reasons)
        if held: excluded.add(name); summary["held_large_delta"]+=1
        else: summary["stable"]+=1
        rows.append({"feed":name,"status":"held_for_source_review" if held else "within_drift_limits",
                     "baseline_rule_count":base,"current_rule_count":len(current),"added_rule_count":len(added),
                     "removed_rule_count":len(removed),"symmetric_delta_ratio":round(ratio,5),"reasons":reasons,
                     "source_identity":"registry URL + declared feed name; publisher labels are not proof of editorial independence"})
    filtered=copy.deepcopy(feed_report)
    for row in filtered.get("feeds",[]):
        if row.get("name") in excluded:
            row["ok"]=False; row["coverage_eligible"]=False; row["trihexomega_discovery_hold"]=True
    result={"schema_version":1,"mode":"discovery_only_feed_drift_guard","summary":summary,
            "excluded_feed_names":sorted(excluded),"feeds":rows,"production_feed_coverage_modified":False,
            "production_rule_changes":0,"publication_authorized":False,
            "notice":"Drift holds affect candidate discovery only. They do not alter the separate production builder or erase a source's history. A maintainer can inspect and explicitly rebaseline a legitimate large source update."}
    return filtered,result

def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--registry",type=Path,default=Path("config/reference_feeds.json")); p.add_argument("--feed-report",type=Path,default=Path("reports/trihexomega-feed-cache-report.json")); p.add_argument("--cache-dir",type=Path,default=Path("reports/trihexomega-feed-cache")); p.add_argument("--baseline",type=Path,default=Path("reports/trihexomega-discovery-baseline.json")); p.add_argument("--policy",type=Path,default=Path("config/trihexomega_policy.json")); p.add_argument("--filtered-report",type=Path,default=Path("reports/trihexomega-drift-screened-feed-report.json")); p.add_argument("--output",type=Path,default=Path("reports/trihexomega-drift-report.json")); a=p.parse_args()
    try:
        registry=json.loads(a.registry.read_text(encoding="utf-8")); report=json.loads(a.feed_report.read_text(encoding="utf-8")); baseline=json.loads(a.baseline.read_text(encoding="utf-8")) if a.baseline.exists() else {"schema_version":2,"feeds":{},"observations":{},"reviewed":{}}; policy=json.loads(a.policy.read_text(encoding="utf-8")); filtered,result=evaluate_drift(registry,report,a.cache_dir,baseline,policy); atomic_json(a.filtered_report,filtered); atomic_json(a.output,result); print(json.dumps(result["summary"],indent=2)); return 0
    except (OSError,ValueError,TypeError,DriftError) as exc: print(f"ERROR: {type(exc).__name__}: {exc}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
