# Feed Drift Guard

The drift guard protects candidate discovery against abrupt changes in a reference feed. It compares exact third-party host-rule fingerprints in the current verified cache snapshot with the previous discovery baseline. A sufficiently large symmetric delta is held out of candidate discovery for inspection.

Important boundaries:

- The guard runs only on fresh or checksum-verified HTTP 304 content.
- Stale, missing, malformed, or cache-mismatched content is excluded.
- Large deltas do not cause the feed to be removed from the separate production builder.
- The guard does not mark rules as malicious or safe.
- The guard does not automatically rebaseline a held feed.
- A maintainer must inspect the source and use a reviewed baseline reset procedure if a legitimate large update is confirmed.

The report is written to `reports/trihexomega-drift-report.json`; candidate discovery uses the derived `reports/trihexomega-drift-screened-feed-report.json`. The original feed health report remains unchanged.
