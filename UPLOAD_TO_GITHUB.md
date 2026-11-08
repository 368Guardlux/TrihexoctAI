# Upload TrihexoctAI — TRIHEXΩ v2.0.0-alpha.5 safely

This archive contains the complete project folder. It is not a partial overlay.

## Recommended upload method

1. Keep the original `368Guardlux/Trihexoct` v1.3.2 repository as your stable backup.
2. Open the separate v2 repository: `https://github.com/368Guardlux/TrihexoctAI`.
3. Create a development branch named `trihexomega-alpha5` from its current `main` branch.
4. Extract this archive on your computer.
5. Open the extracted `TrihexoctAI` folder.
6. Select everything inside it, including `.github/` and all other folders and files.
7. Upload the selected contents to the root of the `trihexomega-alpha5` branch. Do not upload the outer `TrihexoctAI` folder as an extra nested directory.
8. Preserve the directory structure and commit the changes to `trihexomega-alpha5`.
9. Check GitHub Actions and review the maintenance, discovery, and evolution artifacts.

Do not upload this v2 project into the original `368Guardlux/Trihexoct` v1.3.2 repository. Keep the two repositories separate.

## Local validation commands

```bash
python -m pip install --disable-pip-version-check --requirement requirements-ci.txt
python tools/validate_trihexomega_pack.py
python tools/validate_workflows.py
python tools/trihexomega/doctor.py --output reports/trihexomega-doctor.json
python tools/trihexomega/feedback_ledger.py verify --ledger reports/trihexomega-review-feedback.jsonl
python -m unittest discover -s tests -v
```

## Important boundaries

- This is `2.0.0-alpha.5`, not a stable production release.
- All 16 source modules and 833 authored unique active rules are preserved from v1.3.2.
- The packaged filter file is an offline-bootstrap artifact; the archive does not prove the 32 live feeds are currently available.
- The AI provider is optional and not preconfigured. Store its credential only as a GitHub Actions secret.
- The advisory swarm and evolution planner cannot modify or publish production rules.
- The autonomous workflow is read-only and does not replace the production workflow.
- Test Brave compatibility and essential site functions before considering release promotion.
- Do not overwrite the stable production branch until all live checks, independent review, rollback checks, and maintainer approval are complete.
