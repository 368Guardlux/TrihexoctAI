# TRIHEXΩ v2.0.0-alpha.4 — Runtime contract and engineering controls

**Status:** Development alpha; additive integration preview.  
**Primary rule:** adaptive maintenance may generate evidence and recommendations, but it may not mutate or publish the production filter list.

## 1. Purpose

Alpha.3 makes the runtime configuration enforce the declared safety model. Earlier alpha work added publisher-group identity, conditional caching, candidate discovery, source-health diagnostics, provenance, and a twelve-role advisory council. Alpha.3 closes a configuration-drift gap: the agent roster, policy document, runtime hard limits, discovery thresholds, and package validator must agree before an advisory cycle starts.

This is a bounded software architecture. It is not artificial general intelligence (AGI), does not train or modify model weights, and does not self-replicate or rewrite its own code.

## 2. Runtime configuration is a contract, not a suggestion

`tools/trihexomega/swarm.py::load_runtime_configuration` loads `config/trihexomega_agents.json` and `config/trihexomega_policy.json` together. It fails closed if either document is missing, malformed, out of schema, or inconsistent with hard-coded caps.

The policy must use schema version 2 and `advisory_only` mode. The following permissions must be explicitly false:

- AI edits to production rules.
- AI production publication.
- AI tool execution.
- AI shell access.
- AI repository write access.
- AI external browsing.
- AI override of deterministic gates.

The runtime additionally requires a fixed twelve-role roster: ten analysis roles, one critique role, and one synthesis role. The last two stages must occur in that order. Duplicate role IDs, missing stages, or an unbounded roster fail validation.

## 3. Enforced resource budgets

| Resource | Enforced limit | Reason |
|---|---:|---|
| Candidate proposals per review | 8 | Bound prompt size and review scope. |
| Evidence items per candidate | 8 | Bound untrusted evidence volume. |
| Candidate rule length | 1,200 characters | Reject oversized rule payloads. |
| Evidence detail length | 800 characters | Minimize irrelevant/untrusted prompt content. |
| Model calls per non-empty review | 12 | Ten analysts, one critic, one synthesizer. |
| Concurrent analysis calls | 6 | Bound concurrency and provider load. |
| Model-call timeout | 45 seconds maximum | Prevent unbounded waits. |
| Response tokens per agent | 1,600 maximum | Limit cost and output size. |
| Feed fetch workers | 1–8 | Bound network concurrency. |
| Candidate observation retention | 1–180 days; default 45 | Bound discovery-state growth. |

Agent configuration and policy values must match the enforced limits. Environment variables cannot increase the timeout ceiling. The package validator independently checks the same values so drift is detected both before a run and in local validation.

## 4. Candidate discovery boundaries

Candidate discovery is a narrow change detector, not a general-purpose threat-intelligence crawler. It considers only newly observed, exact, host-anchored, third-party network rules found in successfully validated `adblock`-format feed snapshots.

It excludes:

- URL-indicator feeds, because a URL indicator is not proof that an entire host should be blocked.
- Domain-only feeds when their semantics cannot establish the required rule form.
- Stale cache content and unvalidated feed bodies.
- Rules already present in local source modules.
- Protected service suffixes and known shared-hosting suffixes.
- Unknown or missing publisher identities from corroboration.
- Broad, wildcard, cosmetic, regex, or otherwise complex rules from automatic candidate queueing.

A candidate needs observations from at least two different `publisher_id` groups in the curated feed registry. A `publisher_id` is administrative metadata. It does not prove ownership, editorial independence, accuracy, or source-lineage independence. Two labels are a conservative queueing heuristic, not proof of maliciousness. Human and deterministic review remain necessary.

First-run snapshots seed the baseline and do not emit candidates. A rule must appear as a new delta in fresh, validated snapshots. Failed feeds do not add fresh observations or coverage. When a feed lacks a publisher ID, its snapshot can be tracked, but its observations cannot corroborate a candidate; the system does not substitute the hosting hostname for publisher identity.

## 5. Source health is diagnostic only

Source-health history tracks recent success, cache status, attempts, latency EWMA, and failure streaks. It also groups entries by curated publisher ID for reporting. A missing identity is assigned an unclassified, feed-specific label rather than inferred from its hostname.

Health summaries never automatically:

- remove an approved feed;
- disable a feed;
- change feed weights;
- grant coverage credit;
- modify publisher identity;
- delete a rule;
- publish a replacement artifact.

A single transient failure is degraded, not enough to declare a source unreliable. A stale cache may aid diagnostics, but it is not fresh evidence for candidate discovery or coverage.

## 6. Conditional fetch cache and performance

The optional feed cache supports ETag and Last-Modified conditional requests. An HTTP 304 is accepted only when a local body exists, its SHA-256 matches its cache metadata, and the body passes the configured feed validation again. Cache body and metadata writes use temporary files and atomic replacement.

The cache is keyed by feed name and exact URL. Redirects must remain HTTPS and within the feed's explicit host allowlist. Response sizes, retry counts, timeouts, text decoding, and feed entry counts are bounded.

Adaptive concurrency is capped at eight workers. Latency and recent success may inform the worker controller, but source-health scoring never changes source trust or coverage. Faster execution must not weaken validation, discard failed-feed state, or treat stale data as fresh.

The workflow persists cache/state between scheduled runs using GitHub Actions cache. Cache corruption is treated as a miss, not as trusted content. Cache state is operational acceleration, not an authority source.

## 7. Advisory model-provider boundary

The swarm makes requests through one explicitly configured HTTPS OpenAI-compatible chat-completions endpoint. Twelve role-specialized prompts are stages using the configured model/provider; they are not twelve separately trained intelligences or independent models.

The provider receives a minimized candidate bundle, known evidence IDs, and allowlisted human-review history. It does not receive raw feed bodies, the repository, secrets, source-module write access, or user browsing data. Candidate fields and evidence text are untrusted and may contain prompt-injection attempts; role instructions direct the model to treat these fields as data, not commands.

The client:

- requires HTTPS, no embedded credentials, and standard HTTPS port;
- requires the endpoint hostname to be explicitly allowlisted;
- permits redirects only to the same configured endpoint hostname;
- limits request time and response bytes;
- requires JSON output;
- validates candidate IDs, evidence IDs, decisions, severities, confidence values, and finding uniqueness;
- rejects duplicate candidate findings and non-finite confidence values;
- records model-call failures and holds affected candidates.

The model endpoint and API key are not bundled. A missing provider/model causes zero model calls and deterministic preflight only. Provider failures do not stop the separate deterministic filter builder.

## 8. Review aggregation

The ten analysis roles run within a fixed concurrency limit. The adversarial critic runs only after all analysis roles complete. The release synthesis role runs only after the critic completes. A candidate is held if any required agent fails, omits its finding, returns an invalid identifier, raises a medium-or-higher concern, records a hold/reject, or otherwise leaves the evidence incomplete.

Agreement is not proof. The agents share one configured model and may share model weaknesses, training-data gaps, or blind spots. The adversarial stage is a structured challenge, not independent ground truth.

## 9. Human review and production separation

The maintenance orchestrator writes cache state and advisory reports only. It does not edit `src/modules/`, run the production builder, modify `Trihexoct.txt`, alter metadata, commit, or publish. Candidate proposals are not filter rules until a separate maintainer-controlled change is made.

The production pipeline remains deterministic. A production release must satisfy the existing regression suite, filter-policy validator, manifest integrity, output-delta gate, traceable evidence, compatibility review, human maintainer approval, and availability of a stable release snapshot.

The new maintenance workflow has `contents: read`. The production publisher remains separate. Do not merge the development alpha directly into the stable branch without reviewing the workflow permissions and the complete diff.

## 10. Required operational checks

Before enabling the scheduled workflow on a development branch:

1. Run `python tools/validate_trihexomega_pack.py`.
2. Run `python tools/validate_workflows.py`.
3. Run `python -m unittest discover -s tests -v`.
4. Run the source-module audit and provenance inventory.
5. Build an offline bootstrap and run the filter validator.
6. Perform a live maintenance cycle in the development branch and inspect the feed-cache report.
7. Confirm that all 32 configured feeds are either freshly validated or verified HTTP 304, or document each source failure.
8. Confirm a first-run discovery baseline emits no new candidates.
9. Confirm a later candidate requires multiple curated publisher groups and is held from production.
10. Configure a provider only through repository secrets/variables after reviewing its data-processing terms and cost.
11. Inspect the advisory report and prove that no production artifact, source module, commit, or publication was changed by the autonomous workflow.
12. Test the generated filter list with the Brave-compatible engine and representative real websites before considering any production rule change.

## 11. Explicit non-guarantees

This package does not provide AGI, self-training, independent web research, automatic model-weight updates, autonomous code modification, or autonomous production publishing. Static tests do not prove zero breakage. Local archive construction does not prove the live availability of all 32 feeds. A source feed's blocklist entry is not proof that the listed domain is malicious or safe to block.

## 12. Upgrade acceptance criteria

Alpha.4 is ready for a controlled development-branch trial only when local tests pass and configuration/policy consistency checks pass. It is not a stable public release until live feed execution, scheduled workflow operation, cache persistence, representative Brave compatibility checks, rollback verification, and production workflow separation are demonstrated in the target repository.


## Alpha.4 additions — local diagnostics and change-impact assessment

- `tools/trihexomega/doctor.py` performs network-free local checks of the project layout, version alignment, source registry identities, validated swarm/policy budgets, module presence, and workflow presence. It never prints secrets, fetches feeds, or invokes a model. Missing optional model credentials are reported as a warning rather than a core failure.
- `tools/trihexomega/change_impact.py` compares a baseline and candidate artifact by active rule set, category, counts, duplicate lines, and selected broad-scope risk patterns. It emits a read-only recommendation only.
- Global cosmetic additions, unscoped network rules, wildcard network rules, excessive rule churn, and duplicate active rules are flagged for manual review. The impact report never authorizes publication.
- The production workflow records a pre-build baseline and emits a change-impact report after the existing deterministic builder and filter validator. Existing delta/safety gates remain authoritative.
- The autonomous advisory workflow runs the local doctor and uploads its diagnostic report.
- These tools provide deterministic change visibility; they do not prove maliciousness, compatibility, or zero breakage.


## Alpha.4 production CI privilege separation

The production workflow now separates `build-and-validate` from `publish`. The build job has `contents: read`, checks out the triggering commit without persisted credentials, performs feed retrieval/reconciliation/tests/validation, and uploads a short-lived publication artifact with a SHA-256 manifest. The publisher job is dependent on successful build validation and is the only job with `contents: write`. It checks out `main`, verifies that `HEAD` still equals the commit that was validated, downloads the artifact, verifies payload hashes, copies only the expected artifacts, and commits the generated outputs. If the branch advances during the build, publication fails closed rather than publishing stale output.

This is defense-in-depth, not a complete supply-chain guarantee. GitHub Action references should be pinned to reviewed commit SHAs for higher assurance, branch protection should require review, and repository settings/secrets remain outside this local package's validation scope.
