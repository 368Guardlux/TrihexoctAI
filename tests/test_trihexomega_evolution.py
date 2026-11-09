import json
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

TOOLS_ROOT = str(Path(__file__).resolve().parents[1] / "tools")
if TOOLS_ROOT not in sys.path:
    sys.path.insert(0, TOOLS_ROOT)

from trihexomega.evolution_planner import build_evolution_plan, atomic_write_json


class EvolutionPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, data):
        (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def test_missing_reports_are_unknown_not_healthy(self):
        report, state = build_evolution_plan(self.root, self.root / "state.json")
        self.assertEqual(report["recommendation_count"], 0)
        self.assertEqual(report["inputs"]["doctor"], "not_present")
        self.assertFalse(report["automatic_rule_changes"])
        self.assertFalse(report["automatic_publication"])
        self.assertEqual(state["tasks"], {})

    def test_doctor_failure_creates_critical_recommendation(self):
        self.put("trihexomega-doctor.json", {"failed": 2})
        report, _ = build_evolution_plan(self.root)
        row = next(x for x in report["recommendations"] if x["task_key"] == "doctor-failures")
        self.assertEqual(row["priority"], "critical")
        self.assertTrue(row["requires_human_decision"])

    def test_drift_holds_create_source_review_not_production_change(self):
        self.put("trihexomega-drift-report.json", {"summary": {"held_large_delta": 2, "unavailable": 1}})
        report, _ = build_evolution_plan(self.root)
        keys = {x["task_key"] for x in report["recommendations"]}
        self.assertIn("source-drift-review", keys)
        self.assertIn("drift-cache-verification", keys)
        self.assertEqual(report["automatic_rule_changes"], 0)

    def test_confirmed_negative_feedback_creates_category_specific_task(self):
        self.put("trihexomega-learning-report.json", {
            "ledger_valid": True,
            "minimum_labels_for_diagnostic": 8,
            "categories": {"network": {"confirmed_negative": 2, "confirmed_label_count": 3}}
        })
        report, _ = build_evolution_plan(self.root)
        keys = {x["task_key"] for x in report["recommendations"]}
        self.assertIn("false-positive-review:network", keys)
        self.assertIn("feedback-sample:network", keys)

    def test_invalid_feedback_ledger_creates_critical_task(self):
        self.put("trihexomega-learning-report.json", {"ledger_valid": False})
        report, _ = build_evolution_plan(self.root)
        self.assertTrue(any(x["task_key"] == "feedback-ledger-integrity" and x["priority"] == "critical"
                            for x in report["recommendations"]))

    def test_recurrence_is_tracked_but_missing_task_is_not_auto_resolved(self):
        self.put("trihexomega-doctor.json", {"failed": 1})
        state_path = self.root / "state.json"
        report1, state1 = build_evolution_plan(self.root, state_path)
        atomic_write_json(state_path, state1)
        report2, state2 = build_evolution_plan(self.root, state_path)
        task1 = report1["recommendations"][0]
        task2 = report2["recommendations"][0]
        self.assertEqual(task2["task_id"], task1["task_id"])
        self.assertEqual(task2["recurrence_count"], 2)
        self.assertEqual(state2["tasks"][task2["task_id"]]["seen_cycles"], 2)
        # A subsequent report without the doctor failure does not claim resolution.
        (self.root / "trihexomega-doctor.json").unlink()
        report3, state3 = build_evolution_plan(self.root, state_path)
        self.assertEqual(report3["recommendation_count"], 0)
        self.assertIn(task2["task_id"], state3["tasks"])
        self.assertFalse(state3["tasks"][task2["task_id"]]["observed_this_cycle"])
        self.assertEqual(state3["tasks"][task2["task_id"]]["last_observation_state"], "not_observed_this_cycle")
        self.assertIn("never automatically resolved or deleted", state3["state_contract"])

    def test_cycle_gaps_and_incomplete_feed_sync_are_actionable(self):
        self.put("trihexomega-cycle-report.json", {"required_group_gaps": {"adblock": {"required": 2, "available": 1}}})
        self.put("trihexomega-feed-cache-report.json", {"feed_count": 32, "validated_fresh_or_304_count": 29})
        report, _ = build_evolution_plan(self.root)
        keys = {x["task_key"] for x in report["recommendations"]}
        self.assertIn("required-feed-groups", keys)
        self.assertIn("feed-availability", keys)


    def test_direct_cli_entrypoint_creates_plan_and_state(self):
        script = Path(__file__).resolve().parents[1] / "tools" / "trihexomega" / "evolution_planner.py"
        output = self.root / "plan.json"
        state = self.root / "state.json"
        result = subprocess.run(
            [sys.executable, str(script), "--reports-dir", str(self.root),
             "--state", str(state), "--output", str(output)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(output.is_file())
        self.assertTrue(state.is_file())
        plan = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(plan["automatic_publication"])

    def test_report_is_explicitly_advisory_and_bounded(self):
        self.put("trihexomega-doctor.json", {"failed": 1})
        report, _ = build_evolution_plan(self.root)
        self.assertLessEqual(report["recommendation_count"], 40)
        self.assertFalse(report["automatic_code_changes"])
        self.assertFalse(report["automatic_policy_changes"])
        self.assertFalse(report["automatic_rule_changes"])
        self.assertFalse(report["automatic_publication"])
        self.assertTrue(report["human_maintainer_decision_required"])


if __name__ == "__main__":
    unittest.main()
