from __future__ import annotations
import hashlib, json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from trihexomega.feedback_ledger import (LedgerError, record_feedback, verify_ledger,
                                         build_learning_report)
from trihexomega.learning_engine import rank_candidate_bundle
from trihexomega.swarm import sanitize_learning_context, load_runtime_configuration
from trihexomega.drift_guard import evaluate_drift, feed_key
from trihexomega.cache import cache_base, sha256_bytes, atomic_json
from trihexomega.candidate_discovery import fingerprint

class FeedbackLedgerTests(unittest.TestCase):
    def _record(self, path, decision="confirmed_effective_after_trial", candidate_id="cand-1"):
        return record_feedback(path, candidate_id=candidate_id,
            candidate_sha256=hashlib.sha256(candidate_id.encode()).hexdigest(), category="network",
            decision=decision, reviewer="maintainer01", reason="Synthetic test adjudication.",
            evidence_sha256=[hashlib.sha256(b"evidence").hexdigest()])

    def test_empty_ledger_is_valid_and_has_genesis_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=verify_ledger(Path(tmp)/"feedback.jsonl")
            self.assertTrue(result["valid"]); self.assertEqual(result["event_count"],0)
            self.assertEqual(result["head_sha256"],"0"*64)

    def test_recorded_events_form_hash_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"feedback.jsonl"
            self._record(path); self._record(path,decision="rejected",candidate_id="cand-2")
            result=verify_ledger(path)
            self.assertEqual(result["event_count"],2)
            self.assertEqual(result["events"][1]["previous_event_sha256"],result["events"][0]["event_sha256"])

    def test_tampered_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"feedback.jsonl"; self._record(path)
            row=json.loads(path.read_text().strip()); row["reason"]="tampered"
            path.write_text(json.dumps(row)+"\n")
            with self.assertRaises(LedgerError): verify_ledger(path)

    def test_untrusted_or_invalid_feedback_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"feedback.jsonl"
            with self.assertRaises(LedgerError):
                record_feedback(path,candidate_id="x",candidate_sha256="bad",category="network",
                    decision="approved",reviewer="maintainer01",reason="no")
            self.assertFalse(path.exists())

    def test_provisional_beta_approval_is_not_counted_as_confirmed_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"feedback.jsonl"
            self._record(path,decision="approved_for_beta")
            report=build_learning_report(path)
            stats=report["categories"]["network"]
            self.assertEqual(stats["provisional"],1)
            self.assertEqual(stats["confirmed_label_count"],0)
            self.assertEqual(stats["diagnostic_state"],"insufficient_human_outcomes")

    def test_confirmed_human_outcomes_create_diagnostics_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"feedback.jsonl"
            self._record(path,"confirmed_effective_after_trial","a")
            self._record(path,"confirmed_false_positive_after_trial","b")
            report=build_learning_report(path)
            stats=report["categories"]["network"]
            self.assertEqual(stats["confirmed_positive"],1)
            self.assertEqual(stats["confirmed_negative"],1)
            self.assertFalse(report["learning_contract"]["no_automatic_policy_mutation"] is False)

    def test_learning_context_excludes_reviewer_rationale_and_raw_ledger(self):
        safe=sanitize_learning_context({"ledger_valid":True,"categories":{"network":{
            "confirmed_label_count":8,"confirmed_positive":5,"confirmed_negative":3,
            "wilson_95_interval":[0.2,0.8],"diagnostic_state":"mixed"}},
            "reviewer":"private-user","reason":"sensitive raw rationale"})
        serialized=json.dumps(safe)
        self.assertNotIn("private-user",serialized); self.assertNotIn("sensitive raw rationale",serialized)
        self.assertIn("not ground truth",safe["notice"])

class AdaptiveTriageTests(unittest.TestCase):
    def test_triage_prioritizes_fresh_complete_evidence_without_claiming_threat_score(self):
        now=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        bundle={"schema_version":1,"project_version":"test","review_id":"triage",
            "candidates":[
              {"id":"stale","category":"network","rule":"||stale.example^$third-party","evidence":[
                {"publisher_id":"p1","observed_at":"2020-01-01T00:00:00Z"}]},
              {"id":"fresh","category":"network","rule":"||fresh.example^$third-party","evidence":[
                {"publisher_id":"p1","observed_at":now},{"publisher_id":"p2","observed_at":now},
                {"publisher_id":"p3","observed_at":now},{"publisher_id":"p4","observed_at":now}]}
            ]}
        ranked,report=rank_candidate_bundle(bundle,{"categories":{"network":{"confirmed_label_count":0}}})
        self.assertEqual(ranked["candidates"][0]["id"],"fresh")
        self.assertIn("not threat probability",report["ranked_candidates"][0]["score_semantics"])
        self.assertFalse(report["publication_authorized"])

    def test_triage_preserves_every_candidate(self):
        bundle={"schema_version":1,"candidates":[
            {"id":"a","category":"network","rule":"||a.example^$third-party","evidence":[]},
            {"id":"b","category":"network","rule":"||b.example^$third-party","evidence":[]}]}
        ranked,report=rank_candidate_bundle(bundle,None)
        self.assertEqual({x["id"] for x in ranked["candidates"]},{"a","b"})
        self.assertEqual(report["candidate_count"],2)

class DriftGuardTests(unittest.TestCase):
    def _make_feed(self,tmp,current_count=20):
        url="https://feeds.example/list.txt"; name="Synthetic feed"
        feed={"name":name,"url":url,"format":"adblock","max_bytes":100000,"minimum_bytes":200,
              "minimum_entries":10,"groups":["ads"],"publisher_id":"synthetic-publisher"}
        lines=[f"||current{i}.example^$third-party" for i in range(current_count)]
        body=("\n".join(lines)+"\n").encode(); cache_dir=Path(tmp)/"cache"
        base=cache_base(cache_dir,name,url); base.parent.mkdir(parents=True,exist_ok=True)
        base.with_suffix(".txt").write_bytes(body)
        digest=sha256_bytes(body); atomic_json(base.with_suffix(".json"),{"sha256":digest,"url":url,"name":name})
        reg={"feeds":[feed]}; feed_report={"feed_count":1,"feeds":[{"name":name,"ok":True,"coverage_eligible":True,"sha256":digest}]}
        return reg,feed_report,cache_dir,feed

    def test_large_delta_is_held_out_of_discovery_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg,feed_report,cache_dir,feed=self._make_feed(tmp,20)
            old=[fingerprint(f"||old{i}.example^$third-party") for i in range(100)]
            baseline={"schema_version":2,"feeds":{feed_key(feed["name"],feed["url"]):{"rule_fingerprints":old}},
                      "observations":{},"reviewed":{}}
            policy={"drift_guard":{"max_symmetric_delta_ratio":0.35,"minimum_changed_rules":50,
                    "minimum_baseline_rules":80,"maximum_added_rules":500,"maximum_removed_rules":500}}
            filtered,report=evaluate_drift(reg,feed_report,cache_dir,baseline,policy)
            self.assertFalse(filtered["feeds"][0]["ok"])
            self.assertTrue(feed_report["feeds"][0]["ok"])
            self.assertEqual(report["summary"]["held_large_delta"],1)
            self.assertFalse(report["production_feed_coverage_modified"])

    def test_first_observation_is_warmup_not_false_alarm(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg,feed_report,cache_dir,feed=self._make_feed(tmp,20)
            baseline={"schema_version":2,"feeds":{},"observations":{},"reviewed":{}}
            policy={"drift_guard":{"max_symmetric_delta_ratio":0.35,"minimum_changed_rules":50,
                    "minimum_baseline_rules":80,"maximum_added_rules":500,"maximum_removed_rules":500}}
            filtered,report=evaluate_drift(reg,feed_report,cache_dir,baseline,policy)
            self.assertTrue(filtered["feeds"][0]["ok"])
            self.assertEqual(report["feeds"][0]["status"],"warming_baseline")

    def test_missing_verified_cache_is_held_for_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg,feed_report,cache_dir,feed=self._make_feed(tmp,20)
            (cache_dir).mkdir(exist_ok=True)
            cachefiles=list(cache_dir.glob("*.txt")); cachefiles[0].unlink()
            baseline={"schema_version":2,"feeds":{},"observations":{},"reviewed":{}}
            policy={"drift_guard":{"max_symmetric_delta_ratio":0.35,"minimum_changed_rules":50,
                    "minimum_baseline_rules":80,"maximum_added_rules":500,"maximum_removed_rules":500}}
            filtered,report=evaluate_drift(reg,feed_report,cache_dir,baseline,policy)
            self.assertFalse(filtered["feeds"][0]["coverage_eligible"])
            self.assertEqual(report["summary"]["unavailable"],1)

class Alpha5RuntimeTests(unittest.TestCase):
    def test_sixteen_role_runtime_is_bounded_and_policy_consistent(self):
        runtime=load_runtime_configuration(ROOT/"config/trihexomega_agents.json",ROOT/"config/trihexomega_policy.json")
        self.assertEqual(len(runtime["agents"]),16)
        self.assertEqual(runtime["max_model_calls"],16)
        self.assertEqual(runtime["max_parallel_agents"],8)

if __name__ == "__main__": unittest.main()
