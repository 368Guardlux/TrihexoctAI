from __future__ import annotations
import hashlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from trihexomega.cache import atomic_bytes, atomic_json, cache_base
from trihexomega.candidate_discovery import discover_candidates, mark_candidates_reviewed
from trihexomega.policy_engine import screen_bundle
from trihexomega.source_health import evaluate_health
from trihexomega.swarm import load_agents, load_runtime_configuration, run_swarm, SwarmError
from trihexomega.orchestrator import run_cycle


class CandidateDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry_path = self.root / "registry.json"
        self.cache_dir = self.root / "cache"
        self.modules = self.root / "modules"
        self.modules.mkdir()
        self.baseline = self.root / "baseline.json"
        self.output = self.root / "candidate-proposals.json"
        self.feed_report = self.root / "feed-report.json"
        self.url1 = "https://feed-one.example/list.txt"
        self.url2 = "https://feed-two.example/list.txt"
        self.feeds = [
            {"name": "Feed One", "url": self.url1, "max_bytes": 100000, "minimum_bytes": 200,
             "minimum_entries": 10, "format": "adblock", "groups": ["ads"], "required": True, "publisher_id": "publisher-a"},
            {"name": "Feed Two", "url": self.url2, "max_bytes": 100000, "minimum_bytes": 200,
             "minimum_entries": 10, "format": "adblock", "groups": ["ads"], "required": True, "publisher_id": "publisher-b"},
        ]
        self.registry_path.write_text(json.dumps({"feeds": self.feeds, "required_groups": {"ads": 1}}), encoding="utf-8")
        self.old_lines = [f"||old{i}.example^$third-party" for i in range(12)]
        self.new_rule = "||new-observed.example^$third-party"

    def tearDown(self):
        self.temp.cleanup()

    def _feed(self, feed, lines):
        body = ("! validated test feed\n" + "\n".join(lines) + "\n").encode()
        base = cache_base(self.cache_dir, feed["name"], feed["url"])
        atomic_bytes(base.with_suffix(".txt"), body)
        digest = hashlib.sha256(body).hexdigest()
        atomic_json(base.with_suffix(".json"), {"sha256": digest, "validated_at_utc": "2026-11-08T00:00:00Z"})
        return {"name": feed["name"], "ok": True, "coverage_eligible": True, "sha256": digest,
                "cache_status": "refreshed", "attempts": 1, "duration_seconds": 0.1}

    def _report(self, lines1, lines2):
        rows = [self._feed(self.feeds[0], lines1), self._feed(self.feeds[1], lines2)]
        self.feed_report.write_text(json.dumps({"feed_count": 2, "feeds": rows}), encoding="utf-8")

    def _discover(self):
        return discover_candidates(self.registry_path, self.feed_report, self.cache_dir, self.modules,
                                   self.baseline, self.output, min_publishers=2, max_candidates=8)

    def test_candidate_discovery_rejects_weakened_or_oversized_limits(self):
        self._report(self.old_lines, self.old_lines)
        with self.assertRaises(ValueError):
            discover_candidates(self.registry_path, self.feed_report, self.cache_dir, self.modules,
                                self.baseline, self.output, min_publishers=1, max_candidates=8)
        with self.assertRaises(ValueError):
            discover_candidates(self.registry_path, self.feed_report, self.cache_dir, self.modules,
                                self.baseline, self.output, min_publishers=2, max_candidates=9)

    def test_first_run_only_seeds_baseline(self):
        self._report(self.old_lines, self.old_lines)
        report = self._discover()
        bundle = json.loads(self.output.read_text())
        self.assertEqual(report["newly_correlated_candidates"], 0)
        self.assertEqual(bundle["candidates"], [])

    def test_candidate_requires_two_distinct_publishers_across_runs(self):
        self._report(self.old_lines, self.old_lines)
        self._discover()
        self._report(self.old_lines + [self.new_rule], self.old_lines)
        report_one = self._discover()
        self.assertEqual(report_one["newly_correlated_candidates"], 0)
        self._report(self.old_lines + [self.new_rule], self.old_lines + [self.new_rule])
        report_two = self._discover()
        bundle = json.loads(self.output.read_text())
        self.assertEqual(report_two["newly_correlated_candidates"], 1)
        self.assertEqual(bundle["candidates"][0]["rule"], self.new_rule)
        self.assertEqual(len(bundle["candidates"][0]["evidence"]), 2)
        self.assertEqual({x["publisher_id"] for x in bundle["candidates"][0]["evidence"]}, {"publisher-a", "publisher-b"})

    def test_failed_feed_does_not_receive_fresh_coverage_or_observation(self):
        self._report(self.old_lines, self.old_lines)
        self._discover()
        one = self._feed(self.feeds[0], self.old_lines + [self.new_rule])
        two = {"name": "Feed Two", "ok": False, "coverage_eligible": False, "cache_status": "stale_diagnostic_only"}
        self.feed_report.write_text(json.dumps({"feeds": [one, two]}), encoding="utf-8")
        report = self._discover()
        self.assertEqual(report["newly_correlated_candidates"], 0)
        self.assertEqual(report["held_insufficient_publisher_diversity"], 1)

    def test_old_host_only_observations_migrate_using_registry_publisher_ids(self):
        self._report(self.old_lines, self.old_lines)
        self._discover()
        self._report(self.old_lines + [self.new_rule], self.old_lines)
        self._discover()
        baseline = json.loads(self.baseline.read_text())
        entry = next(x for x in baseline["observations"].values() if x["rule"] == self.new_rule)
        for source in entry["sources"]:
            source.pop("publisher_id", None)
        self.baseline.write_text(json.dumps(baseline), encoding="utf-8")
        self._report(self.old_lines + [self.new_rule], self.old_lines + [self.new_rule])
        report = self._discover()
        bundle = json.loads(self.output.read_text())
        self.assertEqual(report["newly_correlated_candidates"], 1)
        self.assertEqual({x["publisher_id"] for x in bundle["candidates"][0]["evidence"]}, {"publisher-a", "publisher-b"})

    def test_existing_local_rule_is_not_reproposed(self):
        (self.modules / "existing.txt").write_text(self.new_rule + "\n", encoding="utf-8")
        self._report(self.old_lines, self.old_lines)
        self._discover()
        self._report(self.old_lines + [self.new_rule], self.old_lines + [self.new_rule])
        report = self._discover()
        self.assertEqual(report["newly_correlated_candidates"], 0)

    def test_missing_publisher_identity_does_not_fallback_to_feed_hostname(self):
        feeds = json.loads(self.registry_path.read_text(encoding="utf-8"))["feeds"]
        for feed in feeds:
            feed.pop("publisher_id", None)
        self.registry_path.write_text(json.dumps({"feeds": feeds, "required_groups": {"ads": 1}}), encoding="utf-8")
        self._report(self.old_lines, self.old_lines)
        self._discover()
        self._report(self.old_lines + [self.new_rule], self.old_lines + [self.new_rule])
        report = self._discover()
        bundle = json.loads(self.output.read_text())
        self.assertEqual(report["newly_correlated_candidates"], 0)
        self.assertEqual(bundle["candidates"], [])
        self.assertGreaterEqual(len(report["source_errors"]), 2)

    def test_reviewed_candidate_is_not_repeated_after_complete_swarm(self):
        self._report(self.old_lines, self.old_lines)
        self._discover()
        self._report(self.old_lines + [self.new_rule], self.old_lines)
        self._discover()
        self._report(self.old_lines + [self.new_rule], self.old_lines + [self.new_rule])
        self._discover()
        bundle = json.loads(self.output.read_text())
        swarm = self.root / "swarm.json"
        swarm.write_text(json.dumps({"mode": "bounded_multi_agent_advisory_review", "ai_enabled": True,
                                     "synthesis": {"swarm_complete": True}, "failures": []}), encoding="utf-8")
        self.assertEqual(mark_candidates_reviewed(self.baseline, self.output, swarm), 1)
        report = self._discover()
        self.assertEqual(report["newly_correlated_candidates"], 0)


class PolicyEngineTests(unittest.TestCase):
    def _candidate(self, rule, urls=None):
        urls = urls or ["https://feed-a.example/list.txt", "https://feed-b.example/list.txt"]
        return {"id": "test-candidate", "rule": rule, "category": "network", "rationale": "Test-only proposal.",
                "evidence": [{"id": f"e{i}", "source": f"source{i}", "url": url,
                              "publisher_id": f"publisher-{i}", "detail": "Synthetic evidence"}
                             for i, url in enumerate(urls)]}

    def test_strict_third_party_host_rule_is_eligible_for_advisory_only(self):
        candidate = self._candidate("||observed.example^$third-party")
        bundle, report = screen_bundle({"schema_version": 1, "project_version": "test", "review_id": "x", "candidates": [candidate]})
        self.assertEqual(len(bundle["candidates"]), 1)
        self.assertEqual(report["eligible_count"], 1)
        self.assertFalse(report["publication_authorized"])

    def test_two_feeds_from_same_publisher_do_not_count_as_independent(self):
        candidate = self._candidate("||tracker.example^$third-party")
        for item in candidate["evidence"]:
            item["publisher_id"] = "same-publisher"
        bundle, report = screen_bundle({"schema_version": 1, "project_version": "test", "review_id": "x", "candidates": [candidate]})
        self.assertEqual(bundle["candidates"], [])
        self.assertIn("publisher", " ".join(report["decisions"][0]["reasons"]).lower())

    def test_protected_domain_is_held(self):
        candidate = self._candidate("||accounts.google.com^$third-party")
        bundle, report = screen_bundle({"schema_version": 1, "project_version": "test", "review_id": "x", "candidates": [candidate]})
        self.assertEqual(bundle["candidates"], [])
        self.assertIn("protected", " ".join(report["decisions"][0]["reasons"]).lower())

    def test_shared_hosting_is_held(self):
        candidate = self._candidate("||tenant.pages.dev^$third-party")
        bundle, report = screen_bundle({"schema_version": 1, "project_version": "test", "review_id": "x", "candidates": [candidate]})
        self.assertEqual(bundle["candidates"], [])
        self.assertIn("shared-hosting", " ".join(report["decisions"][0]["reasons"]).lower())

    def test_screening_rejects_a_weakened_publisher_threshold(self):
        candidate = self._candidate("||tracker.example^$third-party")
        payload = {"schema_version": 1, "project_version": "test", "review_id": "x", "candidates": [candidate]}
        with self.assertRaises(ValueError):
            screen_bundle(payload, min_publishers=1)

    def test_publisher_diversity_is_required_even_across_different_hosts(self):
        candidate = self._candidate("||tracker.example^$third-party", [
            "https://raw.githubusercontent.com/list-a.txt", "https://raw.githubusercontent.com/list-b.txt"])
        for item in candidate["evidence"]:
            item["publisher_id"] = "same-publisher"
        bundle, report = screen_bundle({"schema_version": 1, "project_version": "test", "review_id": "x", "candidates": [candidate]})
        self.assertEqual(bundle["candidates"], [])
        self.assertEqual(report["held_count"], 1)


class SourceHealthTests(unittest.TestCase):
    def test_health_history_moves_from_warmup_to_healthy(self):
        registry = {"feeds": [{"name": "Feed", "url": "https://feed.example/list.txt"}]}
        history = None
        summary = None
        for _ in range(3):
            report = {"feeds": [{"name": "Feed", "ok": True, "coverage_eligible": True,
                                  "duration_seconds": 0.2, "attempts": 1, "cache_status": "not_modified_304"}]}
            summary, history = evaluate_health(report, registry, history)
        self.assertEqual(summary["sources"][0]["status"], "healthy")
        self.assertEqual(summary["healthy_or_warming"], 1)
        self.assertEqual(summary["publisher_group_count"], 1)
        self.assertEqual(summary["publisher_groups"][0]["feed_count"], 1)

    def test_single_transient_failure_is_degraded_not_unreliable(self):
        registry = {"feeds": [{"name": "Feed", "url": "https://feed.example/list.txt", "publisher_id": "pub"}]}
        report = {"feeds": [{"name": "Feed", "ok": False, "coverage_eligible": False,
                              "duration_seconds": 0.2, "attempts": 1, "cache_status": "unavailable"}]}
        summary, _ = evaluate_health(report, registry)
        self.assertEqual(summary["sources"][0]["status"], "degraded")
        self.assertEqual(summary["unreliable"], 0)

    def test_publisher_health_rollup_is_diagnostic_only(self):
        registry = {"feeds": [
            {"name": "Feed A", "url": "https://a.example/list.txt", "publisher_id": "same-owner"},
            {"name": "Feed B", "url": "https://b.example/list.txt", "publisher_id": "same-owner"},
        ]}
        report = {"feeds": [
            {"name": "Feed A", "ok": True, "coverage_eligible": True, "duration_seconds": 0.1, "attempts": 1},
            {"name": "Feed B", "ok": False, "coverage_eligible": False, "duration_seconds": 0.2, "attempts": 2},
        ]}
        summary, _ = evaluate_health(report, registry)
        self.assertEqual(summary["publisher_group_count"], 1)
        self.assertEqual(summary["publisher_groups"][0]["feed_count"], 2)
        self.assertEqual(summary["publisher_groups"][0]["unreliable"], 0)
        self.assertEqual(summary["publisher_groups"][0]["degraded"], 1)
        self.assertEqual(summary["publisher_groups"][0]["mean_success_rate"], 0.5)
        self.assertIn("never automatically removes", summary["policy"])

    def test_health_failure_is_diagnostic_not_a_source_removal(self):
        registry = {"feeds": [{"name": "Feed", "url": "https://feed.example/list.txt"}]}
        history = None
        for _ in range(3):
            report = {"feeds": [{"name": "Feed", "ok": False, "coverage_eligible": False,
                                  "duration_seconds": 0.4, "attempts": 3, "cache_status": "unavailable"}]}
            summary, history = evaluate_health(report, registry, history)
        self.assertEqual(summary["unreliable"], 1)
        self.assertIn("never automatically remove", summary["policy"])


class OrchestratorIsolationTests(unittest.TestCase):
    def test_orchestrator_cycle_is_read_only_for_production_artifacts(self):
        import trihexomega.orchestrator as orchestrator
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry_path = root / "registry.json"
            cache_dir = root / "cache"
            reports_dir = root / "reports"
            modules = root / "modules"
            modules.mkdir()
            sentinel = modules / "sentinel.txt"
            sentinel.write_text("||existing.example^$third-party\n", encoding="utf-8")
            production = root / "Trihexoct.txt"
            production.write_text("! stable sentinel\n||stable.example^$third-party\n", encoding="utf-8")
            before_modules = sentinel.read_bytes()
            before_production = production.read_bytes()
            registry = {"schema_version": 2, "required_groups": {"ads": 1}, "feeds": [
                {"name": "Feed", "url": "https://feed.example/list.txt", "publisher_id": "publisher-one",
                 "max_bytes": 10000, "minimum_bytes": 200, "minimum_entries": 10,
                 "format": "adblock", "groups": ["ads"], "required": True}
            ]}
            registry_path.write_text(json.dumps(registry), encoding="utf-8")

            def fake_registry(_registry, _cache, report_path, _workers, controller_path):
                row = {"name": "Feed", "ok": True, "coverage_eligible": True,
                       "sha256": "a" * 64, "duration_seconds": 0.01, "attempts": 1,
                       "cache_status": "refreshed"}
                report = {"feed_count": 1, "validated_fresh_or_304_count": 1, "selected_workers": 1,
                          "feeds": [row]}
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report), encoding="utf-8")
                controller_path.write_text(json.dumps({"last_workers": 1}), encoding="utf-8")
                return report

            def fake_discovery(_registry, _feed_report, _cache, _modules, _baseline, output_path,
                               min_publishers=2, max_candidates=8, observation_days=45):
                output_path.write_text(json.dumps({"schema_version": 1, "project_version": "test",
                                                   "review_id": "empty", "candidates": []}), encoding="utf-8")
                return {"newly_correlated_candidates": 0, "held_insufficient_publisher_diversity": 0,
                        "candidate_rules_added_to_production": 0, "publication_authorized": False}

            with patch.object(orchestrator, "run_registry", side_effect=fake_registry), \
                 patch.object(orchestrator, "discover_candidates", side_effect=fake_discovery):
                report = run_cycle(registry_path, cache_dir, reports_dir, modules,
                                   ROOT / "config" / "trihexomega_agents.json",
                                   ROOT / "config" / "trihexomega_policy.json", workers=2, skip_ai=True)

            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["production_rule_changes"], 0)
            self.assertFalse(report["publication_authorized"])
            self.assertEqual(sentinel.read_bytes(), before_modules)
            self.assertEqual(production.read_bytes(), before_production)

class DirectCliEntrypointTests(unittest.TestCase):
    def test_workflow_style_direct_python_entrypoints_import_the_package(self):
        for relative in (
            "tools/trihexomega/orchestrator.py",
            "tools/trihexomega/candidate_discovery.py",
            "tools/trihexomega/policy_engine.py",
            "tools/trihexomega/source_health.py",
        ):
            with self.subTest(entrypoint=relative):
                result = subprocess.run([sys.executable, relative, "--help"], cwd=ROOT,
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                self.assertIn("usage:", result.stdout.lower())


class RuntimePolicyTests(unittest.TestCase):
    def test_runtime_configuration_cross_checks_all_caps(self):
        runtime = load_runtime_configuration(ROOT / "config" / "trihexomega_agents.json",
                                             ROOT / "config" / "trihexomega_policy.json")
        self.assertEqual(runtime["max_candidates"], 8)
        self.assertEqual(runtime["max_model_calls"], 16)
        self.assertEqual(runtime["max_parallel_agents"], 8)
        self.assertEqual(runtime["minimum_publisher_groups"], 2)

    def test_runtime_fails_closed_when_policy_enables_production_write(self):
        with tempfile.TemporaryDirectory() as temp:
            policy = json.loads((ROOT / "config" / "trihexomega_policy.json").read_text())
            policy["production_publication_by_ai"] = True
            path = Path(temp) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaises(SwarmError):
                load_runtime_configuration(ROOT / "config" / "trihexomega_agents.json", path)

    def test_runtime_fails_closed_when_policy_and_swarm_caps_diverge(self):
        with tempfile.TemporaryDirectory() as temp:
            policy = json.loads((ROOT / "config" / "trihexomega_policy.json").read_text())
            policy["max_candidates_per_review"] = 25
            path = Path(temp) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaises(SwarmError):
                load_runtime_configuration(ROOT / "config" / "trihexomega_agents.json", path)

class SwarmExpansionTests(unittest.TestCase):
    def test_sixteen_role_roster_and_staged_phases(self):
        agents = load_agents(ROOT / "config" / "trihexomega_agents.json")
        self.assertEqual(len(agents), 16)
        self.assertEqual(sum(a.phase == "analysis" for a in agents), 12)
        self.assertEqual(sum(a.phase == "critique" for a in agents), 3)
        self.assertEqual(agents[-1].phase, "synthesis")

    def test_mocked_swarm_runs_bounded_sixteen_call_protocol(self):
        bundle = {"schema_version": 1, "project_version": "test", "review_id": "test-16",
                  "candidates": [{"id": "c1", "rule": "||candidate.example^$third-party", "category": "network",
                                  "rationale": "Synthetic test only", "evidence": [
                                      {"id": "e1", "source": "source a", "url": "https://a.example/list.txt", "publisher_id": "publisher-a", "detail": "synthetic"},
                                      {"id": "e2", "source": "source b", "url": "https://b.example/list.txt", "publisher_id": "publisher-b", "detail": "synthetic"}]}]}
        class FakeClient:
            model = "test-model"
            enabled = True
            def __init__(self):
                self.calls = 0
            def complete_json(self, system_prompt, payload, max_tokens):
                self.calls += 1
                candidate_bundle = payload.get("candidate_bundle", payload)
                candidates = candidate_bundle["candidates"]
                return {"summary": "Synthetic mocked reviewer response.", "blockers": [],
                        "findings": [{"candidate_id": c["id"], "decision": "approve_for_human_review",
                                      "severity": "low", "confidence": 0.6,
                                      "reason": "Synthetic test response only.",
                                      "evidence_ids": [e["id"] for e in c["evidence"]]} for c in candidates]}
        fake = FakeClient()
        with patch("trihexomega.swarm.OpenAICompatibleClient", return_value=fake):
            report = run_swarm(bundle, ROOT / "config" / "trihexomega_agents.json", max_workers=8)
        self.assertEqual(fake.calls, 16)
        self.assertEqual(report["agent_calls_made"], 16)
        self.assertTrue(report["synthesis"]["swarm_complete"])
        self.assertFalse(report["publication_authorized"])
        self.assertEqual(report["synthesis"]["candidates"]["c1"]["recommended_action"],
                         "eligible_for_deterministic_validation_and_human_review")


if __name__ == "__main__":
    unittest.main()
