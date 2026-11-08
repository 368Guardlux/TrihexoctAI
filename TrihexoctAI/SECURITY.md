# Security policy

Trihexoct is a content-filter list, not a security boundary or antivirus product. Reports about malicious rules, suspicious source URLs, unsafe workflow behavior, or possible credential disclosure should be submitted privately to the repository maintainer rather than posted with secrets in a public issue.

## Update pipeline controls

- Sources must use HTTPS and are read as text only.
- Downloads have per-feed byte caps, timeouts, non-empty checks, and minimum-line checks.
- Required feeds, source-category coverage, overall success thresholds, and large count changes gate automatic publishing.
- The workflow has explicit repository-content permissions; the pull-request workflow is read-only.
- Failed live builds do not replace the published list or advance the last-known-good feed baseline.

These checks reduce supply-chain and accidental-update risks but cannot establish that a maintainer or upstream feed is always trustworthy.
