#!/usr/bin/env python3
"""Tamper-evident, human-adjudicated feedback ledger for TRIHEXΩ.

This is the project's bounded learning input. It stores only reviewer labels,
rule/evidence hashes and short rationales; never subscriber browsing data.
It cannot modify filtering policy, source weights, rules, workflows or releases.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_LEDGER_BYTES = 10_000_000
MAX_EVENTS = 20_000
MAX_REASON = 800
CATEGORIES = {"network", "url_parameter", "cosmetic", "path_or_regex", "other"}
DECISIONS = {"approved_for_beta", "confirmed_effective_after_trial", "rejected",
             "confirmed_false_positive_after_trial", "needs_more_evidence"}
POSITIVE = {"confirmed_effective_after_trial"}
NEGATIVE = {"rejected", "confirmed_false_positive_after_trial"}
NEUTRAL = {"approved_for_beta", "needs_more_evidence"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
REVIEWER = re.compile(r"^[A-Za-z0-9_.@-]{2,80}$")

class LedgerError(ValueError):
    pass

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.stat().st_size > MAX_LEDGER_BYTES:
        raise LedgerError("feedback ledger exceeds 10 MB safety limit")
    events=[]
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            if len(line) > 10_000:
                raise LedgerError(f"feedback event line {line_no} exceeds size limit")
            try:
                row=json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"invalid JSON at ledger line {line_no}") from exc
            if not isinstance(row, dict):
                raise LedgerError(f"ledger line {line_no} must be an object")
            events.append(row)
            if len(events) > MAX_EVENTS:
                raise LedgerError("feedback ledger exceeds 20,000 event limit")
    return events

def verify_ledger(path: Path) -> dict[str, Any]:
    events=_read_events(path)
    previous="0"*64
    seen=set()
    for index,row in enumerate(events,1):
        if row.get("schema_version") != SCHEMA_VERSION:
            raise LedgerError(f"unsupported feedback schema at event {index}")
        if row.get("previous_event_sha256") != previous:
            raise LedgerError(f"hash-chain predecessor mismatch at event {index}")
        claimed=row.get("event_sha256")
        body={k:v for k,v in row.items() if k != "event_sha256"}
        actual=sha256(canonical(body))
        if not isinstance(claimed,str) or not HEX64.fullmatch(claimed) or claimed != actual:
            raise LedgerError(f"event hash mismatch at event {index}")
        event_id=row.get("event_id")
        if not isinstance(event_id,str) or event_id in seen:
            raise LedgerError(f"missing or duplicate event_id at event {index}")
        seen.add(event_id)
        previous=claimed
    return {"valid":True,"event_count":len(events),"head_sha256":previous,"events":events}

def record_feedback(path: Path, *, candidate_id: str, candidate_sha256: str,
                    category: str, decision: str, reviewer: str, reason: str,
                    evidence_sha256: list[str] | None = None, recorded_at_utc: str | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", candidate_id or ""):
        raise LedgerError("candidate_id must be 1..80 safe identifier characters")
    if not HEX64.fullmatch(candidate_sha256 or ""):
        raise LedgerError("candidate_sha256 must be a lowercase SHA-256 digest")
    if category not in CATEGORIES:
        raise LedgerError(f"category must be one of: {', '.join(sorted(CATEGORIES))}")
    if decision not in DECISIONS:
        raise LedgerError(f"decision must be one of: {', '.join(sorted(DECISIONS))}")
    if not REVIEWER.fullmatch(reviewer or ""):
        raise LedgerError("reviewer must be a short handle (2..80 letters, digits, . _ @ -)")
    if not isinstance(reason,str) or not reason.strip() or len(reason.strip()) > MAX_REASON:
        raise LedgerError(f"reason must contain 1..{MAX_REASON} characters")
    evidences=evidence_sha256 or []
    if not isinstance(evidences,list) or len(evidences)>8 or any(not isinstance(x,str) or not HEX64.fullmatch(x) for x in evidences):
        raise LedgerError("evidence_sha256 must contain at most eight SHA-256 digests")
    verified=verify_ledger(path)
    previous=verified["head_sha256"]
    event={
        "schema_version":SCHEMA_VERSION,
        "event_id":sha256(canonical({"candidate_id":candidate_id,"candidate_sha256":candidate_sha256,
                                      "reviewer":reviewer,"decision":decision,"at":recorded_at_utc or utc_now(),
                                      "previous":previous}))[:24],
        "recorded_at_utc":recorded_at_utc or utc_now(),
        "reviewer":reviewer,
        "candidate_id":candidate_id,
        "candidate_sha256":candidate_sha256,
        "category":category,
        "decision":decision,
        "reason":reason.strip(),
        "evidence_sha256":sorted(set(evidences)),
        "previous_event_sha256":previous,
        "label_semantics":"Human review outcome; not proof of maliciousness, global source trust, or universal compatibility.",
    }
    event["event_sha256"]=sha256(canonical(event))
    events=verified["events"]+[event]
    path.parent.mkdir(parents=True,exist_ok=True)
    payload="".join(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n" for row in events)
    tmp=path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w",encoding="utf-8",newline="\n") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists(): tmp.unlink()
    return {"event_id":event["event_id"],"event_sha256":event["event_sha256"],"event_count":len(events)}

def wilson_interval(successes: int, total: int, z: float=1.96) -> tuple[float,float]:
    if total <= 0: return (0.0,1.0)
    p=successes/total; den=1+z*z/total
    center=(p+z*z/(2*total))/den
    margin=z*((p*(1-p)/total+z*z/(4*total*total))**0.5)/den
    return max(0.0,center-margin), min(1.0,center+margin)

def build_learning_report(path: Path, minimum_labels: int=8) -> dict[str, Any]:
    if not 3 <= minimum_labels <= 100:
        raise LedgerError("minimum_labels must be between 3 and 100")
    verified=verify_ledger(path)
    events=verified["events"]
    categories={c:{"confirmed_positive":0,"confirmed_negative":0,"provisional":0,"unresolved":0} for c in sorted(CATEGORIES)}
    for row in events:
        bucket=categories[row["category"]]
        if row["decision"] in POSITIVE: bucket["confirmed_positive"]+=1
        elif row["decision"] in NEGATIVE: bucket["confirmed_negative"]+=1
        elif row["decision"] == "approved_for_beta": bucket["provisional"]+=1
        else: bucket["unresolved"]+=1
    total_pos=sum(v["confirmed_positive"] for v in categories.values())
    total_neg=sum(v["confirmed_negative"] for v in categories.values())
    out={}
    for category,counts in categories.items():
        n=counts["confirmed_positive"]+counts["confirmed_negative"]
        lo,hi=wilson_interval(counts["confirmed_positive"],n)
        mean=(counts["confirmed_positive"]+1)/(n+2) # Jeffreys-like smoothed display prior; not a calibrated model.
        if n < minimum_labels: state="insufficient_human_outcomes"
        elif hi < 0.40: state="review_process_needs_investigation"
        elif lo > 0.70: state="historically_consistent_review_outcomes"
        else: state="mixed_or_uncertain_outcomes"
        out[category]={**counts,"confirmed_label_count":n,"smoothed_positive_fraction":round(mean,4),
                       "wilson_95_interval":[round(lo,4),round(hi,4)],"sample_sufficient_for_diagnostic":n>=minimum_labels,
                       "diagnostic_state":state}
    return {"schema_version":1,"generated_at_utc":utc_now(),"mode":"human_feedback_supervised_diagnostics_only",
            "ledger_valid":True,"ledger_event_count":len(events),"ledger_head_sha256":verified["head_sha256"],
            "confirmed_positive_count":total_pos,"confirmed_negative_count":total_neg,
            "provisional_count":sum(x["provisional"] for x in categories.values()),
            "unresolved_count":sum(x["unresolved"] for x in categories.values()),
            "minimum_labels_for_diagnostic":minimum_labels,"categories":out,
            "learning_contract":{"learns_from":"explicit human review outcomes recorded in a tamper-evident hash-chained ledger",
                "influences":"review prioritization and diagnostic recommendations only",
                "does_not_change":"filter rules, trust scores, policy thresholds, source identities, model weights, or release authority",
                "no_subscriber_telemetry":True,"no_automatic_policy_mutation":True,
                "labels_are_not_ground_truth":"Beta approval is provisional. Only confirmed after-trial outcomes enter the diagnostic numerator/denominator."}}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="command",required=True)
    r=sub.add_parser("record"); r.add_argument("--ledger",type=Path,default=Path("reports/trihexomega-review-feedback.jsonl")); r.add_argument("--candidate-id",required=True); r.add_argument("--candidate-sha256",required=True); r.add_argument("--category",required=True,choices=sorted(CATEGORIES)); r.add_argument("--decision",required=True,choices=sorted(DECISIONS)); r.add_argument("--reviewer",required=True); r.add_argument("--reason",required=True); r.add_argument("--evidence-sha256",action="append",default=[])
    v=sub.add_parser("verify"); v.add_argument("--ledger",type=Path,default=Path("reports/trihexomega-review-feedback.jsonl"))
    s=sub.add_parser("report"); s.add_argument("--ledger",type=Path,default=Path("reports/trihexomega-review-feedback.jsonl")); s.add_argument("--output",type=Path,default=Path("reports/trihexomega-learning-report.json")); s.add_argument("--minimum-labels",type=int,default=8)
    a=p.parse_args()
    try:
        if a.command=="record": result=record_feedback(a.ledger,candidate_id=a.candidate_id,candidate_sha256=a.candidate_sha256,category=a.category,decision=a.decision,reviewer=a.reviewer,reason=a.reason,evidence_sha256=a.evidence_sha256)
        elif a.command=="verify":
            x=verify_ledger(a.ledger); result={"valid":x["valid"],"event_count":x["event_count"],"head_sha256":x["head_sha256"]}
        else:
            result=build_learning_report(a.ledger,a.minimum_labels); a.output.parent.mkdir(parents=True,exist_ok=True); tmp=a.output.with_name("."+a.output.name+".tmp"); tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8"); os.replace(tmp,a.output); result={"output":str(a.output),"ledger_event_count":result["ledger_event_count"],"categories":len(result["categories"])}
        print(json.dumps(result,indent=2)); return 0
    except (OSError,ValueError,TypeError,LedgerError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
