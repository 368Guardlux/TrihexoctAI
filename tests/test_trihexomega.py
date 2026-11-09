from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from trihexomega.cache import FeedCacheError, validate_bytes, validate_feed_url
from trihexomega.swarm import (validate_candidate_bundle, offline_preflight, run_swarm,
                               load_agents, validate_agent_result, SwarmError,
                               SafeProviderRedirectHandler, OpenAICompatibleClient)
from trihexomega.release_guard import evaluate
from trihexomega.cache import validate_registry_config, select_adaptive_workers, fetch_one, SafeRedirectHandler
from trihexomega.provenance import build_inventory
from trihexomega.decision_memory import record_decision, lookup_memory


class FeedCacheTests(unittest.TestCase):
    def test_requires_https(self):
        with self.assertRaises(FeedCacheError):
            validate_feed_url("http://example.com/list.txt")

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(FeedCacheError):
            validate_feed_url("https://user:pass@example.com/list.txt")

    def test_accepts_valid_utf8_text_feed(self):
        body = ("! header\n" + "||ads.example^$third-party\n" * 30).encode("utf-8")
        text, count = validate_bytes(body, {"format": "adblock", "minimum_entries": 10})
        self.assertIn("ads.example", text)
        self.assertEqual(count, 30)

    def test_rejects_html_as_feed(self):
        body = ("<!doctype html>" + "x" * 300).encode("utf-8")
        with self.assertRaises(FeedCacheError):
            validate_bytes(body, {"format": "adblock", "minimum_entries": 1})

    def test_rejects_small_feed(self):
        with self.assertRaises(FeedCacheError):
            validate_bytes(b"! too small\n", {"format": "adblock", "minimum_entries": 1})

    def test_conditional_304_reuses_only_verified_cache(self):
        body = ("! feed header\n" + "||ads.example^$third-party\n" * 30).encode("utf-8")
        feed = {"name": "Example Feed", "url": "https://feeds.example/list.txt", "max_bytes": 10000,
                "minimum_bytes": 200, "minimum_entries": 10, "format": "adblock"}

        class FakeResponse:
            status = 200
            headers = {"ETag": '"v1"', "Last-Modified": "Sun, 08 Nov 2026 00:00:00 GMT", "Content-Type": "text/plain"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def geturl(self): return feed["url"]
            def read(self, limit=-1): return body[:limit]

        class FakeOpener:
            def __init__(self): self.seen_headers = []
            def open(self, request, timeout=20):
                self.seen_headers.append(dict(request.header_items()))
                if request.get_header("If-none-match"):
                    raise HTTPError(request.full_url, 304, "Not Modified", {"ETag": '"v1"'}, None)
                return FakeResponse()

        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            opener = FakeOpener()
            with patch("trihexomega.cache.build_opener", return_value=opener):
                first = fetch_one(feed, cache)
                second = fetch_one(feed, cache)
            self.assertTrue(first["ok"])
            self.assertEqual(first["cache_status"], "refreshed")
            self.assertTrue(second["ok"])
            self.assertEqual(second["cache_status"], "not_modified_304")
            self.assertTrue(second["coverage_eligible"])
            self.assertEqual(len(second["_validated_lines"]), 31)
            self.assertTrue(any("If-None-Match" in h or "If-none-match" in h for h in opener.seen_headers[1]))

    def test_redirect_handler_rejects_unapproved_host_and_http(self):
        handler = SafeRedirectHandler({"feeds.example"})
        with self.assertRaises(FeedCacheError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/list")
        with self.assertRaises(FeedCacheError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://feeds.example/list")


class SwarmTests(unittest.TestCase):
    def setUp(self):
        self.bundle = {
            "schema_version": 1,
            "project_version": "2.0.0-alpha.5",
            "review_id": "test-review",
            "candidates": [{
                "id": "cand-001",
                "rule": "||tracker.example^$third-party",
                "category": "network",
                "rationale": "Test proposal only; not a real threat claim.",
                "evidence": [{
                    "id": "ev-001", "source": "Test source", "url": "https://example.org/report",
                    "publisher_id": "test-publisher", "detail": "Synthetic test evidence.", "observed_at": "2026-11-08"
                }]
            }]
        }

    def test_validates_and_minimizes_bundle(self):
        clean = validate_candidate_bundle(self.bundle)
        self.assertEqual(len(clean["candidates"]), 1)
        self.assertNotIn("secret", json.dumps(clean).lower())

    def test_evidence_must_be_https(self):
        bad = json.loads(json.dumps(self.bundle))
        bad["candidates"][0]["evidence"][0]["url"] = "http://example.org/report"
        with self.assertRaises(Exception):
            validate_candidate_bundle(bad)

    def test_offline_preflight_never_authorizes_publication(self):
        clean = validate_candidate_bundle(self.bundle)
        results = offline_preflight(clean)
        self.assertEqual(results[0]["decision"], "approve_for_human_review")
        self.assertEqual(results[0]["confidence"], 0.0)

    def test_agent_result_rejects_duplicate_candidate_findings(self):
        spec = load_agents(ROOT / "config" / "trihexomega_agents.json")[0]
        finding = {"candidate_id": "cand-001", "decision": "hold", "severity": "low",
                   "confidence": 0.4, "reason": "synthetic", "evidence_ids": ["ev-001"]}
        clean = validate_candidate_bundle(self.bundle)
        with self.assertRaises(SwarmError):
            validate_agent_result(spec, {"findings": [finding, finding]}, clean)

    def test_agent_result_rejects_non_finite_confidence(self):
        spec = load_agents(ROOT / "config" / "trihexomega_agents.json")[0]
        finding = {"candidate_id": "cand-001", "decision": "hold", "severity": "low",
                   "confidence": float("nan"), "reason": "synthetic", "evidence_ids": ["ev-001"]}
        with self.assertRaises(SwarmError):
            validate_agent_result(spec, {"findings": [finding]}, validate_candidate_bundle(self.bundle))

    def test_ai_provider_redirect_cannot_send_credentials_to_another_host(self):
        handler = SafeProviderRedirectHandler({"api.example"})
        with self.assertRaises(SwarmError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://other.example/redirect")

    def test_ai_client_timeout_cannot_exceed_hard_cap(self):
        env = {"TRIHEXOMEGA_AI_BASE_URL": "https://api.example/v1",
               "TRIHEXOMEGA_AI_MODEL": "test-model", "TRIHEXOMEGA_AI_API_KEY": "test-key",
               "TRIHEXOMEGA_AI_ALLOWED_HOSTS": "api.example", "TRIHEXOMEGA_AI_TIMEOUT": "90"}
        with patch.dict("os.environ", env, clear=True):
            client = OpenAICompatibleClient(timeout_cap=45)
        self.assertEqual(client.timeout, 45)

    def test_no_candidates_skips_model_calls(self):
        empty = {"schema_version": 1, "project_version": "2.0.0-alpha.5", "review_id": "empty", "candidates": []}
        report = run_swarm(empty, ROOT / "config" / "trihexomega_agents.json")
        self.assertEqual(report["mode"], "no_candidates_to_review")
        self.assertEqual(report["agent_calls_made"], 0)
        self.assertFalse(report["publication_authorized"])

    def test_rejects_unknown_candidate_id_in_input(self):
        bad = json.loads(json.dumps(self.bundle))
        bad["candidates"][0]["id"] = ""
        with self.assertRaises(Exception):
            validate_candidate_bundle(bad)


class ReleaseGuardTests(unittest.TestCase):
    def test_requires_tests_human_approval_and_swarm_status(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stable = root / "stable.txt"
            candidate = root / "candidate.txt"
            evidence = root / "evidence.json"
            swarm = root / "swarm.json"
            stable.write_text("! stable\n||ads.example^$third-party\n", encoding="utf-8")
            candidate.write_text("! candidate\n||ads.example^$third-party\n", encoding="utf-8")
            evidence.write_text(json.dumps({
                "regression_tests": "passed", "filter_validator": "passed",
                "source_audit": "passed", "compatibility_tests": "passed", "human_approval": True
            }), encoding="utf-8")
            swarm.write_text(json.dumps({"mode": "no_candidates_to_review", "publication_authorized": False}), encoding="utf-8")
            report = evaluate(candidate, stable, evidence, swarm)
            self.assertTrue(report["release_eligible_for_separate_publisher"])
            self.assertFalse(report["publication_authorized"])

    def test_large_delta_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stable = root / "stable.txt"
            candidate = root / "candidate.txt"
            evidence = root / "evidence.json"
            swarm = root / "swarm.json"
            stable.write_text("! stable\n||a.example^$third-party\n", encoding="utf-8")
            candidate.write_text("! candidate\n" + "".join(f"||x{i}.example^$third-party\n" for i in range(5)), encoding="utf-8")
            evidence.write_text(json.dumps({"regression_tests":"passed","filter_validator":"passed","source_audit":"passed","compatibility_tests":"passed","human_approval":True}), encoding="utf-8")
            swarm.write_text(json.dumps({"mode":"no_candidates_to_review","publication_authorized":False}), encoding="utf-8")
            report = evaluate(candidate, stable, evidence, swarm)
            self.assertFalse(report["release_eligible_for_separate_publisher"])
            self.assertTrue(any("delta" in x.lower() for x in report["blockers"]))


class AdaptiveAndProvenanceTests(unittest.TestCase):
    def test_registry_rejects_duplicate_names(self):
        config = {"feeds": [
            {"name": "same", "url": "https://one.example/list.txt", "max_bytes": 1000, "format": "adblock", "groups": ["ads"]},
            {"name": "same", "url": "https://two.example/list.txt", "max_bytes": 1000, "format": "adblock", "groups": ["ads"]}
        ]}
        with self.assertRaises(FeedCacheError):
            validate_registry_config(config)

    def test_adaptive_workers_never_exceed_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            history = Path(temp) / "controller.json"
            chosen, state = select_adaptive_workers(100, history, 32)
            self.assertLessEqual(chosen, 8)
            self.assertLessEqual(state["last_workers"], 8)

    def test_provenance_reports_rule_locations_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            modules = Path(temp) / "modules"
            modules.mkdir()
            (modules / "a.txt").write_text("! heading\n||ads.example^$third-party\n", encoding="utf-8")
            (modules / "b.txt").write_text("||ads.example^$third-party\n||tracker.example^$third-party\n", encoding="utf-8")
            report = build_inventory(modules, "test")
            self.assertEqual(report["module_count"], 2)
            self.assertEqual(report["source_active_line_count"], 3)
            self.assertEqual(report["unique_rule_count"], 2)
            self.assertEqual(report["duplicate_rule_group_count"], 1)

    def test_decision_memory_is_explicit_and_candidate_fingerprinted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "candidates.json"
            memory = root / "memory.jsonl"
            bundle.write_text(json.dumps({
                "schema_version": 1, "project_version": "2.0.0-alpha.5", "review_id": "memory-test",
                "candidates": [{"id": "cand-x", "rule": "||tracker.example^$third-party", "category": "network",
                                "rationale": "test only", "evidence": [{"id": "ev", "source": "test", "url": "https://example.org/evidence", "publisher_id": "test-publisher", "detail": "synthetic"}] }]
            }), encoding="utf-8")
            record_decision(bundle, "cand-x", "needs_more_evidence", "Synthetic test decision", memory)
            matches = lookup_memory(bundle, memory)
            self.assertEqual(matches["cand-x"][0]["decision"], "needs_more_evidence")


if __name__ == "__main__":
    unittest.main()
