#!/usr/bin/env python3
"""Human-feedback learning diagnostics and bounded review-priority adaptation."""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
from typing import Any
from trihexomega.feedback_ledger import build_learning_report, LedgerError

def _parse_date(value: str) -> float | None:
    from datetime import datetime
    try: return datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()
    except (ValueError,TypeError,AttributeError): return None

def rank_candidate_bundle(bundle: dict[str,Any], learning: dict[str,Any] | None=None) -> tuple[dict[str,Any],dict[str,Any]]:
    """Rank review effort, never threat likelihood or permission to block."""
    if not isinstance(bundle,dict) or not isinstance(bundle.get("candidates"),list):
        raise ValueError("candidate bundle schema is invalid")
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc).timestamp(); rows=[]
    categories=(learning or {}).get("categories",{}) if isinstance(learning,dict) else {}
    for candidate in bundle["candidates"]:
        evidence=candidate.get("evidence",[])
        publishers={str(e.get("publisher_id","")) for e in evidence if e.get("publisher_id")}
        times=[_parse_date(str(e.get("observed_at",""))) for e in evidence]
        valid_times=[x for x in times if x is not None]
        age_days=max(0.0,(now-max(valid_times))/86400) if valid_times else 365.0
        freshness=max(0.0,1.0-min(age_days,30.0)/30.0)
        evidence_completeness=min(1.0,len(evidence)/4.0)
        diversity=min(1.0,len(publishers)/4.0)
        category_stats=categories.get(candidate.get("category", "other"),{}) if isinstance(categories,dict) else {}
        sample=int(category_stats.get("confirmed_label_count",0) or 0)
        interval=category_stats.get("wilson_95_interval",[0.0,1.0])
        try: uncertainty=max(0.0,min(1.0,float(interval[1])-float(interval[0])))
        except (ValueError,TypeError,IndexError): uncertainty=1.0
        # Review-effort score: reward fresh, complete evidence; modestly prioritize
        # poorly characterized categories. It is explicitly not a maliciousness score.
        score=45*freshness+30*evidence_completeness+15*diversity+10*uncertainty
        if sample < 8: score += 5.0
        score=max(0.0,min(100.0,score))
        rows.append({"candidate_id":str(candidate.get("id","")),"category":str(candidate.get("category","other")),
                     "review_priority_score":round(score,2),"evidence_count":len(evidence),
                     "curated_publisher_label_count":len(publishers),"youngest_evidence_age_days":round(age_days,2),
                     "category_feedback_sample_size":sample,"category_feedback_interval_width":round(uncertainty,4),
                     "score_semantics":"Review scheduling priority only; not threat probability, maliciousness, safety, confidence, or a filtering decision."})
    rows.sort(key=lambda r:(-r["review_priority_score"],r["candidate_id"]))
    ids=[x["candidate_id"] for x in rows]; by_id={c["id"]:c for c in bundle["candidates"]}
    ranked={**bundle,"candidates":[by_id[i] for i in ids]}
    report={"schema_version":1,"mode":"deterministic_learning_informed_review_triage",
            "candidate_count":len(rows),"ranked_candidates":rows,
            "learning_context_used":bool(learning),"production_rule_changes":0,"publication_authorized":False,
            "notice":"Ranking allocates review attention only. It cannot classify a domain as malicious, change a rule, alter policy, or authorize publication."}
    return ranked,report

def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--candidates",type=Path,default=Path("reports/trihexomega-candidate-proposals-screened.json")); p.add_argument("--learning-report",type=Path,default=Path("reports/trihexomega-learning-report.json")); p.add_argument("--output",type=Path,default=Path("reports/trihexomega-candidate-proposals-ranked.json")); p.add_argument("--report",type=Path,default=Path("reports/trihexomega-triage-report.json")); a=p.parse_args()
    try:
        bundle=json.loads(a.candidates.read_text(encoding="utf-8")); learning=json.loads(a.learning_report.read_text(encoding="utf-8")) if a.learning_report.exists() else None
        ranked,report=rank_candidate_bundle(bundle,learning); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(ranked,indent=2)+"\n",encoding="utf-8"); a.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); print(json.dumps({"candidate_count":report["candidate_count"],"output":str(a.output),"publication_authorized":False},indent=2)); return 0
    except (OSError,ValueError,TypeError,LedgerError) as exc: print(f"ERROR: {exc}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
