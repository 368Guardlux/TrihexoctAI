# Coverage and Overlap Policy — TRIHEXΩ v2.0.0-alpha.5

## Published rule categories

1. Named third-party advertising exchanges, ad servers, demand/supply platforms, and attribution infrastructure.
2. Named third-party analytics, campaign measurement, session replay, and telemetry endpoints where the host/path has a clear measurement purpose.
3. Recognized marketing attribution and click identifiers only. Generic authentication, session, user, redirect, referrer, `source`, and deep-link parameters are excluded.
4. Explicit ad-slot/widget cosmetics and known site-specific sponsored-result selectors. Global consent, login, payment, video, social-content, and generic modal/overlay hiding is excluded.
5. Narrow historical browser-mining indicators as supplementary signals; they are not a replacement for security software.

## Overlap reconciliation

The deterministic builder fetches approved HTTPS references and indexes only rule shapes it can interpret conservatively. It removes a local rule only for exact filter matches, simple compatible hostname coverage, or recognized attribution-parameter names/prefixes. It does not infer equivalence for arbitrary regexes, cosmetic selectors, scriptlets, redirects, CSP, or complex modifiers. Upstream content is never copied wholesale into the generated file.

The curated reference set is not a guarantee that a browser has exactly the same subscriptions enabled. Where coverage cannot be established, the builder preserves the local rule rather than guessing.

## Feed health and anomaly controls

- Registry URLs must use HTTPS; names and URLs must be unique; formats are recognized and per-source byte caps are enforced.
- Transient network errors receive bounded retries; malformed content and invalid UTF-8 are rejected.
- Per-feed counts are evaluated against a rolling median of prior successful observations.
- Large source-count shifts block publishing pending maintainer review.
- Required source groups and minimum feed success thresholds must pass.
- Unit tests, source-policy validation, output category gates, duplicate detection, change-impact review, and output manifest checks are required before a production workflow commits.
- A separate output-delta gate blocks large live output changes unless an explicit manual override is reviewed.
- Output is written atomically; failed gates do not replace the published list or advance the production last-known-good baseline.

## Candidate discovery and publisher identity

New advisory candidates are restricted to exact third-party host rules observed in fresh, validated adblock-format feed deltas. Corroboration uses curated `publisher_id` groups from the registry; multiple feeds from one publisher ID count once. Publisher labels are annotations, not proof of ownership, editorial independence, or correctness. Candidate discovery is advisory-only and cannot add production rules.

## Drift and feedback

The alpha.5 drift guard compares a fresh verified feed snapshot with its discovery baseline. A large change is held out of candidate discovery only; it does not alter production feed coverage. Automatic rebaseline is disabled.

Human-feedback outcomes are stored in a hash-chained ledger. Confirmed after-trial outcomes inform aggregate diagnostics and review ordering only. They do not change rules, trust, source weights, policy, or publication authority.

## Evolution planning

The deterministic evolution planner converts current reports into a bounded engineering backlog. Recurrence is tracked across cycles; absence from the latest cycle does not auto-resolve or delete a task. Its priorities are engineering attention order, not threat probability.

## Limitations

Overlap reduction is deliberately conservative. Static tests are not a complete Brave adblock-rust parser and do not replace live-site testing. Third-party network rules can affect legitimate widgets or embedded services. Keep Brave's built-in security protections and maintained subscriptions enabled.
