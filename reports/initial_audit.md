# Source audit summary

The two supplied starting files were syntactically much larger than a simple tracking list, but several apparent “advanced” sections operated through global code injection and broad heuristics.

## Source measurements

| Source | Approx. physical lines | Active unique rules reported by the source audit | Notable classes |
|---|---:|---:|---|
| Published Trihexoct starting list | 1,513 | 1,032 | 570 network/host entries, 298 cosmetic entries, 78 URL-parameter rules; categories overlap |
| Alternate “neural-style” list | 807 | 416 | 83 host entries, 236 cosmetic entries, 58 URL-parameter rules; categories overlap |
| Project v1.1.0 offline build | 783 | 631 network, 73 URL-parameter, 69 cosmetic, 10 path/regex | Third-party scoped network rules, recognized attribution parameters, explicit ad cosmetics, narrow paths |

Counts depend on exact-line de-duplication and do not measure effectiveness. The starting files contained global scriptlet/API modifications, broad CSP and socket rules, raw IP patterns, `$important` overrides, generic endpoint regexes, and cosmetic rules affecting consent/paywall/social/video UI. These were not retained merely to preserve the count.

## Resulting project policy

The starting rules were screened and normalized, then augmented with explicit ad-tech inventory and modular build infrastructure. All network rules must be third-party scoped; parameter removals are restricted to known attribution IDs; cosmetic rules must identify explicit ad elements; source rules must pass the same policy in both builder and linter.

The bootstrap build is offline. Its report deliberately sets `reference_coverage_complete` to false. Online overlap reconciliation is only established after the GitHub workflow fetches reference feeds and completes successfully.


## Version 1.1 additions

The project now references the ShadowWhisperer Ads and Tracking domain lists for conservative domain coverage comparison. The official OpenPhish Community feed is included as a health/hash-only reference, not as an output source and not as domain-wide overlap evidence. These changes respond to the list families visible in the original screenshots while preserving the rule-safety policy.


## Version 1.2.1 reliability audit

- Source modules: 16.
- Unique source rules before reference reconciliation: 831.
- Exact duplicates between source modules: 0.
- Static policy violations: 0.
- Regression tests: 38.
- Generated bootstrap rule breakdown: 662 network, 77 recognized attribution parameters, 83 cosmetic, and 9 narrow path rules.
- Reference registry: 32 feeds; the current local build is still an offline bootstrap and therefore has not established live feed overlap.
- Added a deterministic `reports/source-inventory.json` record containing module hashes, category counts, duplicate findings, and policy findings.
- Corrected the online workflow to rebuild before validating the canonical output, preserve a tracked rolling baseline, report partial versus complete reference reconciliation accurately, and include source audit output in CI artifacts/commits.


## Version 1.3.0 output-change safety gate

- Current offline bootstrap: 833 unique active rules across 16 modules (662 network, 77 URL-parameter, 85 cosmetic, 9 path/regex).
- Added a separate live output-delta gate: if the candidate changes more than 40% of the previously published active-rule set, the build aborts before replacing `Trihexoct.txt` or advancing the reference baseline.
- `reports/rule-delta.json` records added/removed counts, changed ratio, examples, threshold, and whether a manual override was used.
- The manual override is independent from the feed-count anomaly override. Neither override bypasses rule-policy validation, source-health requirements, or final output validation.
- Offline checks: 46 unit tests pass; static filter validator passes; live reference reconciliation remains unverified until GitHub Actions completes successfully.

## TRIHEXΩ v2.0.0-alpha.1 package audit

- Current package version: 2.0.0-alpha.1.
- Inherited deterministic source modules: 16.
- Authored source rules: 833.
- Exact source duplicates: 0.
- Static policy violations: 0.
- Bundled generated filter: 833 unique active rules (662 network, 77 URL-parameter, 85 cosmetic, 9 path/regex).
- The canonical bundled artifact remains an offline bootstrap; no live feed reconciliation is inferred from the 32-entry registry count.
- TRIHEXΩ advisory, conditional-cache, provenance, and release-guard components are included, but the cache adapter and AI provider are not activated by default.
- Local tests do not establish Brave runtime compatibility or zero live-site breakage.
