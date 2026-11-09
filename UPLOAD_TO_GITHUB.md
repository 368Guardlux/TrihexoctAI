# Upload TRIHEXΩ v2.0.0-alpha.5 safely

This archive contains the complete project folder. It is not a partial overlay.

## Recommended upload method

1. Back up the existing stable v1.3.2 repository.
2. Create a separate GitHub development branch, for example `trihexomega-alpha5`.
3. Extract the complete archive on your computer.
4. Open the extracted `Trihexoct_Guardlux_Project_TRIHEXOMEGA_v2_0_0_ALPHA5` folder.
5. Select the contents inside the folder, including hidden `.github/` content if your file manager supports it.
6. Upload the contents to the repository root of the development branch. Do not add an extra enclosing project folder level.
7. Preserve the complete structure and all existing files in the archive.
8. Commit the upload to the development branch.
9. Check the Actions runs and review the uploaded cycle/evolution artifacts.

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
