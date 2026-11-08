# TRIHEXΩ v2.0.0-alpha.5 — Full Project Release Status

**Package version:** `2.0.0-alpha.5`  
**Channel:** Development alpha / integration preview  
**Stable subscription URL:** `https://raw.githubusercontent.com/368Guardlux/Trihexoct/main/Trihexoct.txt`

## Alpha.5 additions

- Added a deterministic evolution planner that turns operations, feed-health, drift, feedback, discovery, triage, swarm, and change-impact reports into a bounded engineering backlog.
- Added recurrence history for improvement tasks. Missing tasks are marked not observed in the latest cycle, never auto-resolved or silently deleted.
- Added hard limits for evolution-state size and recommendation count; oversized state requires maintainer-reviewed archival.
- Integrated evolution-plan generation into the read-only maintenance orchestrator.
- Persisted compact evolution recurrence state in the autonomous workflow cache and uploaded the generated plan as an artifact.
- Added a workflow preflight that verifies the human-feedback ledger before learning diagnostics are used.
- Updated package validation to enforce the evolution planner's no-mutation permissions and workflow integration.
- Rewrote current README and quick-start documentation to align version, role counts, test instructions, and self-learning limits.

## Retained TRIHEXΩ capabilities

- Sixteen bounded advisory roles: twelve analysts, three critics, one synthesis guardian.
- Candidate discovery from fresh validated feed deltas, curated publisher grouping, deterministic pre-screening, and per-feed discovery drift guard.
- Conditional HTTP cache, verified 304 handling, content checksums, atomic cache writes, bounded adaptive fetching, and source-health history.
- Hash-chained human-feedback ledger and deterministic review-priority adaptation.
- Operations Doctor, change-impact analyzer, rule provenance, and controlled release checks.
- Separate read-only maintenance/advisory workflow and restricted production publisher job.

## Preserved filtering baseline

All sixteen source modules are preserved byte-for-byte from the supplied v1.3.2 baseline. The 833 authored unique active rules remain unchanged. The packaged `Trihexoct.txt` contains the alpha.5 version header but no new AI-generated rules.

| Baseline measurement | Value |
|---|---:|
| Source modules | 16 |
| Authored unique active rules | 833 |
| Network rules | 662 |
| URL-parameter rules | 77 |
| Cosmetic rules | 85 |
| Path/regex rules | 9 |
| Configured reference feeds | 32 |

## Local validation

The complete alpha.5 local suite contains 125 tests. The final package validation report records the exact test, Python compilation, workflow parsing, doctor, builder, source-parity, and archive-integrity outcomes.

## Not established by this archive

- Current online availability or successful reconciliation of all 32 reference feeds.
- A live model-provider response or production AI review quality.
- Real Brave parser compatibility or zero website breakage.
- Long-term scheduled-workflow reliability or persistent GitHub cache behavior.
- Production integration of all optional TRIHEXΩ components.

The bundled metadata is an offline-bootstrap snapshot. Archive generation did not fetch the live feeds.

## Release rule

Upload alpha.5 to a separate development branch. Run the GitHub-hosted maintenance workflow, inspect all per-feed results and the evolution plan, configure a model provider only if desired, test representative websites in Brave, and verify cache persistence and rollback. Require maintainer approval, compatibility evidence, a stable snapshot, and passing deterministic release gates before promoting any changes to the stable production branch.
