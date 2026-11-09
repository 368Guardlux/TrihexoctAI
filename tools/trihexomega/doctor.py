#!/usr/bin/env python3
"""TRIHEXΩ local operations doctor; read-only and network-free."""
from __future__ import annotations
import argparse, json, os, platform, sys
from datetime import datetime, timezone
from pathlib import Path

_TOOLS_ROOT=str(Path(__file__).resolve().parents[1])
if _TOOLS_ROOT not in sys.path: sys.path.insert(0,_TOOLS_ROOT)
from trihexomega.swarm import load_runtime_configuration


def check(name: str, ok: bool, detail: str, severity: str='error') -> dict:
    return {'name':name,'status':'pass' if ok else ('warning' if severity=='warning' else 'fail'),'detail':detail}


def diagnose(root: Path) -> dict:
    checks=[]
    def add(n,ok,d,s='error'): checks.append(check(n,bool(ok),d,s))
    required=['VERSION','Trihexoct.txt','Trihexoct.meta.json','config/reference_feeds.json',
      'config/trihexomega_agents.json','config/trihexomega_policy.json','tools/build_filter.py',
      'tools/validate_filter.py','src/modules','.github/workflows']
    missing=[x for x in required if not (root/x).exists()]
    add('required_project_layout',not missing,('all required paths present' if not missing else 'missing: '+', '.join(missing)))
    version=(root/'VERSION').read_text(encoding='utf-8').strip() if (root/'VERSION').exists() else ''
    meta={}
    try: meta=json.loads((root/'Trihexoct.meta.json').read_text(encoding='utf-8'))
    except Exception: pass
    filter_text=(root/'Trihexoct.txt').read_text(encoding='utf-8-sig',errors='replace') if (root/'Trihexoct.txt').exists() else ''
    add('version_consistency',bool(version and meta.get('project_version')==version and f'! Version: {version}' in filter_text),
        f'VERSION={version or "missing"}; metadata and filter header must match')
    registry={}
    try: registry=json.loads((root/'config/reference_feeds.json').read_text(encoding='utf-8'))
    except Exception: pass
    feeds=registry.get('feeds',[]) if isinstance(registry,dict) else []
    missing_ids=[str(f.get('name','unnamed')) for f in feeds if not isinstance(f.get('publisher_id'),str) or not f.get('publisher_id')]
    add('reference_registry_identity',bool(feeds) and not missing_ids,
        f'{len(feeds)} configured feed entries; {len(missing_ids)} missing curated publisher IDs')
    try:
        runtime=load_runtime_configuration(root/'config/trihexomega_agents.json',root/'config/trihexomega_policy.json')
        add('runtime_policy_consistency',True,
            f'{len(runtime["agents"])} roles; max {runtime["max_candidates"]} candidates; {runtime["max_model_calls"]} calls; {runtime["max_fetch_workers"]} fetch workers')
    except Exception as exc:
        add('runtime_policy_consistency',False,f'{type(exc).__name__}: {exc}')
    modules=list((root/'src/modules').glob('*.txt')) if (root/'src/modules').exists() else []
    add('source_module_presence',bool(modules),f'{len(modules)} source modules found')
    workflows=list((root/'.github/workflows').glob('*.yml'))+list((root/'.github/workflows').glob('*.yaml')) if (root/'.github/workflows').exists() else []
    add('workflow_presence',bool(workflows),f'{len(workflows)} workflow files found')
    provider=bool(os.environ.get('TRIHEXOMEGA_AI_API_KEY') and os.environ.get('TRIHEXOMEGA_AI_MODEL'))
    add('optional_model_provider',provider,'configured' if provider else 'not configured; deterministic maintenance remains available','warning')
    return {'schema_version':1,'generated_at_utc':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
      'project_version':version,'mode':'local_read_only_network_free_diagnostics','python_version':platform.python_version(),
      'checks':checks,'passed':sum(x['status']=='pass' for x in checks),'warnings':sum(x['status']=='warning' for x in checks),
      'failed':sum(x['status']=='fail' for x in checks),'network_requests_made':0,'secrets_printed':False,
      'production_changes':0,'publication_authorized':False,
      'notice':'This doctor checks local configuration and layout only. It does not fetch feeds, invoke an AI model, run Brave, or certify website compatibility.'}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=Path('.')); p.add_argument('--output',type=Path,default=Path('reports/trihexomega-doctor.json')); p.add_argument('--strict',action='store_true'); a=p.parse_args()
    try:
      result=diagnose(a.root.resolve()); a.output.parent.mkdir(parents=True,exist_ok=True); tmp=a.output.with_name('.'+a.output.name+'.tmp'); tmp.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); tmp.replace(a.output)
      print(json.dumps({k:result[k] for k in ('project_version','passed','warnings','failed','network_requests_made','publication_authorized')},indent=2))
      return 1 if result['failed'] or (a.strict and result['warnings']) else 0
    except (OSError,ValueError) as exc:
      print(f'ERROR: {type(exc).__name__}: {exc}',file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
