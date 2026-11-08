# Security and Adaptation Model — TRIHEXΩ v2.0.0-alpha.5

## Security objectives

TRIHEXΩ is designed to maintain a supplementary filter list without unnecessarily breaking legitimate websites or giving untrusted feeds or model output authority over production. The primary security goals are source authenticity, evidence integrity, least privilege, reproducibility, bounded resource use, privacy minimization, and recoverability.

## Trust boundaries

1. **Reference feeds are untrusted data.** Only registry-approved HTTPS URLs are fetched. Redirects, content type, size, encoding, cache validators, and SHA-256 integrity are checked. Feed content is parsed as data and never executed.
2. **Candidate indicators are untrusted.** They are normalized, fingerprinted, screened for scope and shared infrastructure, and required to have registry-declared publisher-group observations. Publisher IDs are metadata annotations, not proof of independent ownership or correctness.
3. **Model output is untrusted.** It is bounded by time, output size, schema, candidate IDs, evidence IDs, and call budgets. The model has no tools, browsing, shell, repository, secret, or publication authority.
4. **Human feedback is sensitive operational metadata.** It is append-only and hash-chained. Raw rationale is not passed to the model; only allowlisted aggregate diagnostics are used. No subscriber browsing history is collected.
5. **Production publishing is privileged.** Build and validation are read-only. A separate publisher verifies the source commit and artifact checksums before writing approved generated artifacts.

## Controlled learning

The feedback ledger provides supervised operational learning from explicit human outcomes. Confirmed after-trial outcomes inform aggregate category diagnostics; provisional approval and unresolved evidence are not counted as confirmed labels. Feedback can change candidate review ordering only.

The evolution planner converts machine-readable operations reports into engineering actions. It does not write code, rules, policy, source trust, workflow permissions, or releases. It tracks recurrence; disappearance from one report is not treated as resolution.

No part of this system trains model weights or constitutes AGI. One configured LLM endpoint is used per run; role prompts do not create independently trained or independent models.

## Fail-closed behavior

- Missing or stale source evidence does not count as current coverage.
- Large feed drift is held out of candidate discovery, not silently accepted.
- Unknown or ambiguous candidate scope is held.
- Partial or malformed swarm review is held.
- Invalid feedback ledger is not used.
- Missing reports are unknown, not healthy.
- Change-impact reports do not authorize publication.
- Failed validation cannot replace the last-known-good artifact.

## Website compatibility

Blocking a host can affect unrelated services on shared infrastructure. URL indicators are not automatically expanded to registrable-domain blocks. Generic cookie, consent, login, authentication, payment, checkout, accessibility, modal, or navigation elements must not be hidden by broad cosmetic rules. No static policy can guarantee zero breakage; representative real-browser tests are required.

## Credential and CI controls

Never commit provider secrets. Use GitHub Actions secrets and least-privilege permissions. Keep model-provider host allowlists narrow. Do not allow model-generated content to control URLs, tool execution, shell commands, workflow configuration, or credentials. Review action references, dependencies, branch protection, and repository settings.
