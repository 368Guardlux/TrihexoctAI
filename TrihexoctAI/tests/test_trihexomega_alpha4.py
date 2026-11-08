from __future__ import annotations
import json, tempfile, unittest, subprocess, sys
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from trihexomega.change_impact import analyze
from trihexomega.doctor import diagnose

class ChangeImpactTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def files(self,old,new):
        a=self.root/'old.txt'; b=self.root/'new.txt'; a.write_text('! old\n'+'\n'.join(old)+'\n'); b.write_text('! new\n'+'\n'.join(new)+'\n'); return a,b
    def test_identical_lists_are_low_risk_but_never_authorized(self):
        rules=['||ads.example^$third-party']; a,b=self.files(rules,rules); r=analyze(a,b,ROOT/'config/trihexomega_policy.json')
        self.assertEqual(r['recommendation'],'low_risk_for_independent_review'); self.assertFalse(r['publication_authorized'])
    def test_global_cosmetic_addition_is_held(self):
        a,b=self.files(['||ads.example^$third-party'],['||ads.example^$third-party','##.modal'])
        r=analyze(a,b,ROOT/'config/trihexomega_policy.json'); self.assertEqual(r['recommendation'],'hold_for_manual_review'); self.assertGreaterEqual(len(r['review_flags']),1)
    def test_unscoped_network_addition_is_held(self):
        a,b=self.files(['||ads.example^$third-party'],['||ads.example^$third-party','||new.example^'])
        r=analyze(a,b,ROOT/'config/trihexomega_policy.json'); self.assertEqual(r['recommendation'],'hold_for_manual_review')
    def test_large_delta_is_held(self):
        old=[f'||old{i}.example^$third-party' for i in range(100)]; new=old+[f'||new{i}.example^$third-party' for i in range(10)]
        a,b=self.files(old,new); r=analyze(a,b,ROOT/'config/trihexomega_policy.json'); self.assertEqual(r['recommendation'],'hold_for_manual_review')
    def test_duplicates_are_held(self):
        a,b=self.files(['||ads.example^$third-party'],['||ads.example^$third-party','||ads.example^$third-party'])
        r=analyze(a,b,ROOT/'config/trihexomega_policy.json'); self.assertGreater(r['candidate']['duplicate_lines'],0)

class Alpha4CliTests(unittest.TestCase):
    def test_new_tools_run_as_direct_script_entrypoints(self):
        for rel in ("tools/trihexomega/doctor.py", "tools/trihexomega/change_impact.py"):
            with self.subTest(entrypoint=rel):
                proc=subprocess.run([sys.executable,rel,"--help"],cwd=ROOT,text=True,capture_output=True,timeout=10)
                self.assertEqual(proc.returncode,0,msg=proc.stderr)
                self.assertIn("usage:",proc.stdout.lower())

class DoctorTests(unittest.TestCase):
    def test_doctor_reports_local_checks_without_network_or_secret_disclosure(self):
        r=diagnose(ROOT); self.assertEqual(r['failed'],0); self.assertEqual(r['network_requests_made'],0); self.assertFalse(r['secrets_printed']); self.assertFalse(r['publication_authorized'])

if __name__=='__main__': unittest.main()
