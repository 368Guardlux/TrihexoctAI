# Contributing

## Rule requirements

Contributions should add a narrowly justified rule with a clear purpose. Prefer named ad/measurement endpoints and explicit ad-slot markers; scope network filters to third-party traffic. Do not add a rule solely to increase the line count.

Never submit global JavaScript/scriptlets, page API mutation, CSP rewrites, blanket socket/WebRTC/STUN/TURN blocks, raw IP-range denies, `$important` overrides, auth/session/redirect/deep-link parameter removal, or cosmetic rules that hide consent, login, checkout, comments, or player controls.

## Workflow

1. Edit an appropriate file in `src/modules/`.
2. Add or update a regression test if changing policy behavior.
3. Run unit tests, an offline build, and the linter:

   ```bash
   python -m pip install -r requirements-ci.txt
python tools/validate_workflows.py
python -m unittest discover -s tests -v
   python tools/build_filter.py --output /tmp/Trihexoct.txt --report /tmp/build-report.json
   python tools/validate_filter.py /tmp/Trihexoct.txt
   ```

4. Review the generated diff. Never hand-edit `Trihexoct.txt`.
5. For live reference updates, use the scheduled/manual GitHub workflow; do not bypass a failed feed-health or anomaly gate without reading the report.

## False positives

Report the affected URL, expected behavior, actual behavior, and the smallest reproducible test. Avoid posting session IDs, authentication tokens, cookies, or other secrets in an issue.
