# Groundwork working process

Version 0.5 · October 1, 2026 · Local checks installed; hooks and remote CI deferred.

[Architecture guide and diagrams](ARCHITECTURE.md) explain the flow, decision authority and checker boundaries.

1. Orient using AGENTS.md, Project Context, and the source map. Inspect the current diff and preserve unrelated work.
2. Establish the requested outcome, scope, preserved behavior, and acceptance checks. Retrieve existing answers before asking questions. Pause for consequential unresolved intent; routine implementation choices can proceed within scope.
3. Make the change in the owning source. Keep Demo/Live separation, product evidence boundaries, and generated/runtime files intact.
4. Verify at the appropriate level. Offline commands are described in docs/TECHNICAL_OVERVIEW.md. UI changes also need browser review. Live evaluations and benchmarks need a bounded authorized scope. Record failures and skipped checks honestly.
5. Review documentation impact once the change is coherent. Update affected current descriptions, assess Project Context, and record consequential decisions where needed. A justified no-impact result is valid; there is no requirement to rewrite every document.
6. Report the result, verification, open issues, and continuation point. Commit or publish only within the user’s authorized scope.

## Decisions

Use [the decision criteria and index](../decisions/README.md#when-a-record-is-needed) during planning/discovery and at the existing completion checkpoint. The criteria concern durable behavior, conflicting guidance, important boundaries/authority/architecture/evaluation, or consequential tradeoffs. A proposed decision remains proposed until its named decider accepts it. Routine edits do not need records. Keep project state as the present overview, not a concatenation of decision history.

## Checks and known failures

`python -m unittest discover` runs the documented mocked unit suite. `python evals/runner.py --validate-only` validates the dataset. `python evals/runner.py --deterministic-only` runs behavior cases and writes reports plus the evaluation index. Use the project environment and the current technical guide.

The October 1 local verification passes all 26 deterministic cases after correcting an obsolete winner expectation with presentation-continuity criteria. The offline runner still returns nonzero for any failing suite; there is no failure allowlist. Compare new reports with Project Context and preserve historical failures.

## Documentation impact review

Requires Git and Node.js 22 or newer; no npm installation or package manifest is needed. Run from the repository root:

```sh
node scripts/check-docs.mjs --report
node scripts/check-docs.mjs --draft
```

When the configured generated guidance is stale, read the authoritative decision and repair its generated sections before completing the check. Missing paperwork does not prohibit starting investigation or independent authorized work. Pause dependent implementation only when actual intent or authority is unresolved.

Report selects affected documentation from docs/documentation-map.json. Draft creates docs/documentation-review.json with pending groups and a short Project Context assessment; it never approves them. Read the affected documents against the change, then complete each group with status `reviewed`, disposition `updated` or `no-impact`, a specific reason (at least 20 characters), evidence paths from the change, and the actual reviewer. Updated means every document in that group changed. Add further targets when semantic impact exceeds the map.

Complete projectContext with status `reviewed`, boolean changed, reason, and reviewer. A true answer requires a Project Context edit. Complete decisionImpact as described below, then run:

```sh
node scripts/check-docs.mjs
```

A relevant source, document, mapping, or checker edit invalidates the associated review. Redrafting retains unaffected groups at the same base; a new base requires fresh review. The short context assessment covers the whole nonhistorical change. This checks working-tree contents, not an exact staged index; --staged is rejected. Use --base COMMIT for a prior starting revision after committing. A clean default result is not historical certification.

History under artifacts is excluded from ordinary review contents, while artifacts/evals/INDEX.md routes to evaluation guidance. Unknown changed paths require classification. The checker binds coverage and evidence to changed contents; people or agents still perform semantic review. It does not prove approval identity or narrative truth.

## Decision impact assessment

The same report/draft/check commands include one decisionImpact assessment in the schema-v3 receipt. Legacy v2 receipts require explicit --migrate before drafting; migration preserves original bytes and creates pending assessments. Drafting never accepts a decision.

Fields: status (`pending` or `reviewed`), disposition, reason (at least 20 characters), reviewer, records (repository-relative paths), and a checker-generated fingerprint.

| Disposition | Record requirement |
| --- | --- |
| none | No record needed; records is empty. Explain why the task preserves decisions. |
| existing | Link unchanged records already present at the selected base. |
| update | Link at least one changed existing record, with no new records. |
| create | Link at least one new record; other relevant existing/updated records may also be linked. |

Use paths like docs/decisions/DR-0001-scrolling-conflict.md, never the index or template. For mixed work use the most expansive disposition: create, then update, then existing. Explain the individual records in the brief reason. Reuse a record instead of duplicating a decision just to complete the form.

After choosing or changing record links, rerun --draft to bind them before marking the assessment reviewed. Draft retains the prior explanation and links for the same base but reopens review when the nonhistorical change, linked record contents, decision guidance, rules or checker changes. Like Project Context, this is one whole-task assessment: any nonhistorical edit merits reconsidering its short answer. Unaffected documentation groups retain their separate reviews; there is no repeated assessment after each edit. A new base starts a new assessment.

The checker validates completeness, record paths/existence, create/update/existing claims relative to the base, and freshness. It does not decide whether an ADR is semantically needed, validate its rationale, authenticate the decider, change its status, or authorize implementation. Follow the record's actual approval requirements before dependent work. An honest none result is valid.

## Isolated offline verification

Use the project Python environment:

```sh
.venv/bin/python scripts/verify-offline.py
# Optional narrower runs:
.venv/bin/python scripts/verify-offline.py --only unit
.venv/bin/python scripts/verify-offline.py --only eval
```

The runner snapshots tracked and nonignored untracked working files into a temporary directory, excluding environment files, historical artifacts, logs, caches/worktrees and runtime metadata. Deleted tracked files stay deleted; symlinks require explicit handling. It runs unit tests and/or deterministic Core v2 there, with no credential environment, dotenv disabled, and Python socket connections blocked. Generated logs, reports, and index stay in the temporary copy. summary.json records the source revision, file hashes, and exit codes. The copied evaluation report itself lacks Git metadata; use summary.json for provenance. Keep desired evidence before OS temporary-file cleanup. This copies current files but does not lock against concurrent edits; rerun after edits settle.

This is a runner for trusted repository tests, not an adversarial sandbox: subprocesses launched by tests are not network-sandboxed by its Python guard. It makes no claim of browser, live model, latency, cost, or production verification. It does not run the documentation check automatically; both checks are required at completion.

Exit status remains nonzero for any failing suite, with no failure allowlist. Offline baseline reproduction is a scoped finding, not a green complete product evaluation.

## Groundwork regression checks

```sh
node --test scripts/check-docs.test.mjs
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s scripts/groundwork-tests -v
```

Run these when modifying the checker, routing, or offline runner. They exercise review lifecycle, stale evidence, preservation of unrelated reviews, repository routing, historical boundaries, snapshot exclusions, and failure reporting.

No local hook, remote CI gate, nightly job, or live evaluation is added by this installation. No commits or publication are implied by passing checks.

## Installation verification

[Pass 3](../work/PASS-3.md) records isolated frontend, engine-copy, and evaluation trials. Relevant edits reopened reviews; unrelated reviews survived. The engine-copy trial failed two literal-copy assertions, which were retained rather than suppressed. Product defects and unmeasured acceptance areas remain explicit in Project Context. These trials do not establish independent cold-start usability or long-term drift prevention.

## Generated guidance and receipt migration

[Generated guidance and v3 contracts](GROUNDWORK-CONTRACTS.md) define the installed source, mapping and receipt formats. The scrolling pilot renders the accepted DR-0001 summary and rationale into four marked destinations. The full record retains the original decision source and evidence.

```sh
node scripts/sync-guidance.mjs --check
node scripts/sync-guidance.mjs --write
# Only for a known legacy v2 receipt:
node scripts/check-docs.mjs --migrate
```

Generate after source edits, review the diff, then draft and complete the existing review. Generation never accepts a proposal or changes an ADR. Missing/invalid fields stop that generation/checkpoint, not all work. Unknown migration fields stop the migration with original contents preserved. Use source records directly when summaries are stale; resolve genuine uncertainty before dependent implementation.

Migration preserves the receipt base and original bytes in docs/history/groundwork-migrations/, resets all assessments to pending and fingerprints to null, and never writes application files. Run draft with the preserved base after migrating. V3 schema rejects unknown fields. Migration rejects --base and other mode combinations. A valid v3 migration is a no-op. No hook or remote gate was installed.

The bundled validator requires no runtime npm install. Schema maintainers use the [pinned build procedure](../../.groundwork/core/groundwork/README.md). For this pass, 43 checker tests and two offline-runner regression tests passed; [evidence](../work/PRE-EXTRACTION-FIX-PASS-2.md). Eight [Fix Pass 3 workflow trials](../work/PRE-EXTRACTION-FIX-PASS-3.md) passed. Independent-agent and long-term effectiveness remain unmeasured.

## Canonical installation

Groundwork 0.1.0-rc.3 is pinned by `.groundwork/installation.json`. Shared implementation lives in `.groundwork/core/`; the scripts entry points are wrappers. Configuration, this project-specific workflow, decision records and offline runner remain project-owned. Follow the [shared workflow](../../.groundwork/core/WORKFLOW.md) and [decision criteria](../../.groundwork/core/DECISIONS.md). Changes to shared core belong upstream, followed by a reviewed update; do not edit managed copies. The superseded script modules are preserved under `docs/history/pre-canonical-groundwork/` as historical evidence, not active tooling. Local regression fixtures now load the installed core.
