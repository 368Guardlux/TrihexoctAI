import json, re, sys, time, unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_filter import validate_rule, normalize_rule, active, rule_category, simple_host_rule, domain_covers, param_name, check_anomalies, build_coverage_index, feed_entry_active, validate_feed_config, fetch_feeds_concurrently, atomic_write_text, calculate_output_delta, active_rules_from_text, output_delta_gate_passes
from audit_source_modules import build_inventory
from validate_workflows import load_workflow, validate_all_workflows
from validate_workflows import load_workflow, validate_all_workflows

class FilterPolicyTests(unittest.TestCase):
    def test_global_scriptlets_rejected(self): self.assertIsNotNone(validate_rule('*##+js(set-constant, ga, noopFunc)'))
    def test_csp_and_socket_rejected(self):
        self.assertIsNotNone(validate_rule('*$csp=object-src none'))
        self.assertIsNotNone(validate_rule('||x.test^$websocket,third-party'))
    def test_important_rejected(self): self.assertIsNotNone(validate_rule('||ads.test^$third-party,important'))
    def test_ip_range_rejected(self): self.assertIsNotNone(validate_rule('||192.0.2.*^$third-party'))
    def test_functional_parameter_rejected(self): self.assertIsNotNone(validate_rule('*$removeparam=token'))
    def test_attribution_parameter_allowed(self): self.assertIsNone(validate_rule('*$removeparam=fbclid'))
    def test_known_utm_regex_allowed(self): self.assertIsNone(validate_rule('*$removeparam=/^utm_/'))
    def test_unknown_param_regex_rejected(self): self.assertIsNotNone(validate_rule('*$removeparam=/^.*id$/'))
    def test_cookie_and_paywall_cosmetics_rejected(self):
        self.assertIsNotNone(validate_rule('##[class*="cookie-banner"]'))
        self.assertIsNotNone(validate_rule('##.subscribe-overlay'))
    def test_explicit_ad_slot_cosmetic_allowed(self): self.assertIsNone(validate_rule('##[data-ad-slot]'))
    def test_generic_modal_rejected(self): self.assertIsNotNone(validate_rule('##.modal'))
    def test_network_normalization_scopes_third_party(self):
        self.assertEqual(normalize_rule('||ads.example^'),'||ads.example^$third-party')
    def test_host_match(self):
        self.assertTrue(domain_covers('||example.com^','||sub.example.com^$third-party'))
    def test_resource_limited_rule_not_universal(self):
        self.assertFalse(domain_covers('||example.com^$script,third-party','||sub.example.com^$third-party'))
    def test_param_parser(self): self.assertEqual(param_name('*$removeparam=fbclid'),'fbclid')
    def test_anomaly_gate(self):
        statuses=[{'name':'A','ok':True,'active_lines':1000}]
        self.assertEqual(len(check_anomalies(statuses,{'A':{'active_lines':100}})),1)
    def test_reference_config(self):
        config=json.loads((ROOT/'config/reference_feeds.json').read_text())
        names={f['name'] for f in config['feeds']}
        self.assertTrue({'EasyList','EasyPrivacy','Peter Lowe Ad Servers'}<=names)
        self.assertTrue({'ads','privacy','security'}<=set(config['required_groups']))
        self.assertGreaterEqual(len(config['feeds']),32)
        self.assertTrue(all(f['url'].startswith('https://') for f in config['feeds']))
        self.assertTrue(all(int(f.get('max_bytes',0)) >= 200 for f in config['feeds']))

    def test_url_indicator_feed_is_health_only_not_domain_wide_coverage(self):
        candidates={'||example.com^$third-party'}
        exact, hosts, params, prefixes = build_coverage_index(
            ['https://example.com/malicious/specific-page'],
            'url-indicators', candidates, {'example.com'}
        )
        self.assertEqual(set(), exact)
        self.assertEqual({}, hosts)
        self.assertEqual(set(), params)
        self.assertEqual(set(), prefixes)

    def test_domain_feed_can_prove_host_overlap(self):
        candidates={'||ads.example^$third-party'}
        exact, hosts, params, prefixes = build_coverage_index(
            ['ads.example'], 'domains', candidates, {'ads.example'}
        )
        self.assertEqual(set(), exact)
        self.assertIn('ads.example', hosts)
        self.assertEqual(['||ads.example^'], hosts['ads.example'])


    def test_reference_feed_entry_counting_is_format_aware(self):
        self.assertTrue(feed_entry_active('ads.example', 'domains'))
        self.assertFalse(feed_entry_active('# header', 'domains'))
        self.assertFalse(feed_entry_active('this is not a domain', 'domains'))
        self.assertTrue(feed_entry_active('https://phish.example/login', 'url-indicators'))
        self.assertFalse(feed_entry_active('not-a-url', 'url-indicators'))
        self.assertFalse(feed_entry_active('! list comment', 'adblock'))
        self.assertFalse(feed_entry_active('# plain comment', 'adblock'))
        self.assertTrue(feed_entry_active('##[data-ad-slot]', 'adblock'))

    def test_extended_reference_registry(self):
        config=json.loads((ROOT/'config/reference_feeds.json').read_text())
        by_name={f['name']: f for f in config['feeds']}
        self.assertEqual('domains', by_name['ShadowWhisperer Ads Domains']['format'])
        self.assertEqual('domains', by_name['ShadowWhisperer Tracking Domains']['format'])
        self.assertEqual('url-indicators', by_name['OpenPhish Community URL Indicators (health only)']['format'])
        self.assertGreaterEqual(len(config['feeds']), 32)

    def test_sources_are_unique_and_pass_policy(self):
        src=ROOT/'src/modules'; rules=[]
        for p in src.glob('*.txt'):
            rules += [normalize_rule(x) for x in p.read_text().splitlines() if active(x)]
        self.assertEqual(len(rules),len(set(rules)))
        issues=[(x,validate_rule(x)) for x in rules if validate_rule(x)]
        self.assertEqual([],issues)


    def test_path_network_rules_are_normalized_to_third_party(self):
        rule=normalize_rule('*/amp-analytics-*.js')
        self.assertIn('$third-party',rule)
        self.assertIsNone(validate_rule(rule))

    def test_unbounded_cross_site_regex_is_rejected(self):
        self.assertIsNotNone(validate_rule(r'/^https?:\/\/.*\/api\/(?:track|collect)/$third-party'))
        self.assertIsNotNone(validate_rule(r'/^https?:\/\/[^\/]+\/telemetry/$third-party'))

    def test_slash_delimited_url_regex_requires_third_party_scope(self):
        self.assertIsNotNone(validate_rule('/api/v1/telemetry/$xhr'))
        self.assertIsNone(validate_rule(r'/^https?:\/\/example\.com\/telemetry\/$third-party'))

    def test_rolling_median_anomaly_gate(self):
        statuses=[{'name':'Feed A','ok':True,'active_lines':1000}]
        baseline={'Feed A':{'history':[{'active_lines':100},{'active_lines':105},{'active_lines':110}]}}
        anomalies=check_anomalies(statuses,baseline,history_samples=7)
        self.assertEqual(len(anomalies),1)
        self.assertEqual(anomalies[0]['previous_active_lines'],105)

    def test_feed_registry_rejects_duplicate_urls(self):
        config={'feeds':[
            {'name':'A','url':'https://example.com/list-a','max_bytes':500,'format':'adblock','groups':['ads']},
            {'name':'B','url':'https://example.com/list-a','max_bytes':500,'format':'adblock','groups':['privacy']}
        ],'required_groups':{'ads':1}}
        with self.assertRaises(RuntimeError): validate_feed_config(config)

    def test_feed_registry_rejects_non_https_source(self):
        config={'feeds':[{'name':'A','url':'http://example.com/list','max_bytes':500,'format':'adblock','groups':['ads']}], 'required_groups':{'ads':1}}
        with self.assertRaises(RuntimeError): validate_feed_config(config)

    def test_parallel_fetch_returns_registry_order(self):
        feeds=[{'name':'first'},{'name':'second'},{'name':'third'}]
        def fake_fetch(feed,retries=None):
            # Force out-of-order completion to test deterministic result ordering.
            time.sleep({'first':0.03,'second':0.01,'third':0}[feed['name']])
            return [feed['name']],{'name':feed['name'],'ok':True,'active_lines':100}
        with patch('build_filter.fetch_feed',side_effect=fake_fetch):
            results=fetch_feeds_concurrently(feeds,max_workers=3,retries=1)
        self.assertEqual([status['name'] for _,status in results],['first','second','third'])

    def test_extended_reference_sources_match_visible_configuration(self):
        config=json.loads((ROOT/'config/reference_feeds.json').read_text())
        names={f['name'] for f in config['feeds']}
        self.assertIn('HaGeZi Threat Intelligence Full',names)
        self.assertIn('uBlock Origin Quick Fixes',names)
        self.assertIn('Fuck Fuckadblock (legacy reference)',names)
        self.assertIn('Fuck Fuckadblock Mining (legacy reference)',names)

    def test_module_count_includes_added_complementary_modules(self):
        module_names={p.name for p in (ROOT/'src'/'modules').glob('*.txt')}
        self.assertIn('27-additional-ad-delivery-and-attribution.txt',module_names)
        self.assertIn('32-session-replay-and-user-measurement.txt',module_names)
        self.assertIn('72-explicit-ad-slots-and-widgets.txt',module_names)

    def test_source_inventory_has_no_duplicate_or_policy_violating_rules(self):
        inventory=build_inventory()
        self.assertEqual(inventory['exact_duplicate_count'],0)
        self.assertEqual(inventory['policy_violation_count'],0)
        self.assertGreaterEqual(inventory['totals']['active_rules'],500)
        self.assertGreaterEqual(inventory['source_module_count'],16)

    def test_bootstrap_is_explicitly_not_claimed_as_online_reconciled(self):
        text=(ROOT/'Trihexoct.txt').read_text(encoding='utf-8')
        self.assertIn('Build mode: OFFLINE BOOTSTRAP',text)
        meta=json.loads((ROOT/'Trihexoct.meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['build_mode'],'offline-bootstrap')
        self.assertFalse(json.loads((ROOT/'reports/bootstrap-build-report.json').read_text(encoding='utf-8'))['reference_coverage_complete'])

    def test_published_bootstrap_avoids_global_scriptlet_csp_and_socket_rules(self):
        rules=[x.strip() for x in (ROOT/'Trihexoct.txt').read_text(encoding='utf-8').splitlines() if active(x)]
        for rule in rules:
            self.assertNotIn('##+js(',rule.lower())
            self.assertNotIn('$csp=',rule.lower())
            self.assertNotIn('$websocket',rule.lower())
            self.assertNotIn('$important',rule.lower())

    def test_validator_manifest_tracks_current_project_version(self):
        import hashlib
        meta=json.loads((ROOT/'Trihexoct.meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['project_version'],(ROOT/'VERSION').read_text().strip())
        self.assertEqual(meta['source_module_count'],len(list((ROOT/'src'/'modules').glob('*.txt'))))
        actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src'/'modules').glob('*.txt'))}
        self.assertEqual(meta['source_module_sha256'],actual)
        self.assertEqual(meta['reference_registry_sha256'],hashlib.sha256((ROOT/'config'/'reference_feeds.json').read_bytes()).hexdigest())

    def test_feed_registry_rejects_unknown_format(self):
        config={'feeds':[{'name':'A','url':'https://example.com/a','max_bytes':500,'format':'executable','groups':['ads']}], 'required_groups':{}}
        with self.assertRaises(RuntimeError): validate_feed_config(config)

    def test_feed_registry_rejects_unknown_group(self):
        config={'feeds':[{'name':'A','url':'https://example.com/a','max_bytes':500,'format':'adblock','groups':['mystery']}], 'required_groups':{}}
        with self.assertRaises(RuntimeError): validate_feed_config(config)

    def test_atomic_writer_preserves_exact_text(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'nested'/'filter.txt'
            atomic_write_text(target,'! test\n||example.test^$third-party\n')
            self.assertEqual(target.read_text(encoding='utf-8'),'! test\n||example.test^$third-party\n')
            self.assertEqual([p.name for p in target.parent.iterdir()],['filter.txt'])

    def test_output_delta_ignores_comments_and_metadata(self):
        old='! Version: 1\n||ads.example^$third-party\n*$removeparam=fbclid\n'
        new='! Version: 2\n||ads.example^$third-party\n*$removeparam=gclid\n'
        d=calculate_output_delta(old,new)
        self.assertEqual(2,d['changed_count'])
        self.assertEqual(1,d['added_count'])
        self.assertEqual(1,d['removed_count'])
        self.assertEqual(1.0,d['changed_ratio'])

    def test_output_delta_empty_previous_is_safe(self):
        d=calculate_output_delta(None,'! Title: test\n||ads.example^$third-party\n')
        self.assertEqual(0,d['previous_active_rules'])
        self.assertEqual(1,d['candidate_active_rules'])
        self.assertEqual(1.0,d['changed_ratio'])

    def test_active_rule_set_ignores_comments_and_blanks(self):
        self.assertEqual({'||ads.example^$third-party'}, active_rules_from_text('! header\n\n||ads.example^$third-party\n'))

    def test_output_delta_policy_is_configured(self):
        cfg=json.loads((ROOT/'config/reference_feeds.json').read_text())
        self.assertLessEqual(cfg['policy']['max_published_rule_change_ratio'], 0.5)
        self.assertEqual('manual-review-required-for-large-live-reconciliation-change',cfg['policy']['output_delta_gate'])

    def test_google_search_cosmetics_are_site_scoped(self):
        for rule in ['google.*##.uEierd','google.*##.ads-ad']:
            self.assertIsNone(validate_rule(rule))
            self.assertTrue(rule.startswith('google.*##'))


    def test_large_output_delta_requires_manual_approval(self):
        delta={'changed_ratio':0.75}
        self.assertFalse(output_delta_gate_passes(delta,0.40,True,False))
        self.assertTrue(output_delta_gate_passes(delta,0.40,True,True))

    def test_small_output_delta_passes_without_override(self):
        self.assertTrue(output_delta_gate_passes({'changed_ratio':0.12},0.40,True,False))

    def test_delta_gate_does_not_apply_to_nonpublishing_dry_run(self):
        self.assertTrue(output_delta_gate_passes({'changed_ratio':9.0},0.40,False,False))


class WorkflowIntegrityTests(unittest.TestCase):
    def test_workflow_yaml_parses_and_all_steps_are_complete(self):
        self.assertEqual([], validate_all_workflows())

    def test_main_workflow_triggers_and_scoped_publish_permission_match_design(self):
        workflow = load_workflow(ROOT / '.github' / 'workflows' / 'main.yml')
        events = workflow['on']
        self.assertTrue({'workflow_dispatch', 'schedule', 'push'}.issubset(events))
        build = workflow['jobs']['build-and-validate']
        publisher = workflow['jobs']['publish']
        self.assertEqual('read', build['permissions']['contents'])
        self.assertEqual('write', publisher['permissions']['contents'])
        self.assertEqual('build-and-validate', publisher['needs'])
        build_steps = build['steps']
        step_names = {step.get('name') for step in build_steps}
        self.assertIn('Validate workflow YAML and step structure', step_names)
        self.assertIn('Fetch reference feeds, reconcile overlap, and build', step_names)
        self.assertIn('Analyze filter change impact against current published baseline', step_names)
        checkout = next(step for step in build_steps if step.get('uses', '').startswith('actions/checkout@'))
        self.assertIs(checkout['with']['persist-credentials'], False)
        publish_steps = publisher['steps']
        publish_uses = {step.get('uses') for step in publish_steps}
        self.assertTrue(any(value and value.startswith('actions/download-artifact@') for value in publish_uses))
        publish_runs = '\n'.join(step.get('run', '') for step in publish_steps)
        self.assertIn('sha256sum --check', publish_runs)
        self.assertIn('git push origin HEAD:main', publish_runs)


class WorkflowIntegrityTests(unittest.TestCase):
    def test_workflow_yaml_parses_and_all_steps_are_complete(self):
        self.assertEqual([], validate_all_workflows())

    def test_main_workflow_triggers_and_publish_permissions_match_design(self):
        workflow = load_workflow(ROOT / '.github' / 'workflows' / 'main.yml')
        events = workflow['on']
        self.assertTrue({'workflow_dispatch', 'schedule', 'push'}.issubset(events))
        build = workflow['jobs']['build-and-validate']
        publisher = workflow['jobs']['publish']
        self.assertEqual('read', build['permissions']['contents'])
        self.assertEqual('write', publisher['permissions']['contents'])
        self.assertEqual('build-and-validate', publisher['needs'])
        build_steps = build['steps']
        step_names = {step.get('name') for step in build_steps}
        self.assertIn('Validate workflow YAML and step structure', step_names)
        self.assertIn('Fetch reference feeds, reconcile overlap, and build', step_names)
        self.assertIn('Analyze filter change impact against current published baseline', step_names)
        checkout = next(step for step in build_steps if step.get('uses', '').startswith('actions/checkout@'))
        self.assertIs(checkout['with']['persist-credentials'], False)
        publish_steps = publisher['steps']
        publish_uses = {step.get('uses') for step in publish_steps}
        self.assertTrue(any(value and value.startswith('actions/download-artifact@') for value in publish_uses))
        publish_runs = '\n'.join(step.get('run', '') for step in publish_steps)
        self.assertIn('sha256sum --check', publish_runs)
        self.assertIn('git push origin HEAD:main', publish_runs)

    def test_rule_category_mapping_is_stable(self):
        self.assertEqual('network', rule_category('||ads.example^$third-party'))
        self.assertEqual('url_parameter', rule_category('*$removeparam=fbclid'))
        self.assertEqual('cosmetic', rule_category('##[data-ad-slot]'))
        self.assertEqual('path_or_regex', rule_category('*/pixel.gif$image,third-party'))

if __name__=='__main__': unittest.main()
