# DR-0003 Assess decision impact in the existing review

Status: Accepted approach; implemented and verified in two bounded passes
Date: October 1, 2026
Decider: J.L. (approach and scope); Codex (implementation details)
Scope: Groundwork's local impact review in this repository

## Context

Documentation impact and Project Context already have a grouped, content-bound checkpoint. ADR creation used broad agent instructions without a recorded impact assessment. Joel wants the same impact-review framework applied to decisions, without a separate system or excessive ceremony.

## Options and recommendation

- Keep instructions alone: simplest, but omission is not visible in the checkpoint.
- Extend the current receipt and checker: one short decision assessment with record links and existing freshness checks. Selected.
- Add a classifier, separate workflow or agent: adds machinery before evidence that it is needed. Deferred.

## Decision and rationale

Use explicit criteria for durable behavior, conflicts, consequential boundaries/authority/architecture/evaluation changes, and tradeoffs future work must understand. Apply them when decisions arise in planning/discovery and reconcile once at completion. Routine implementation of established decisions is exempt from new records.

Add decisionImpact to the existing receipt with none/existing/update/create, a reason, reviewer, linked records and a fingerprint. Use the existing commands. Bind the assessment to the whole current nonhistorical change and linked record content. Validate record work relative to the chosen base without treating assessment as approval.

Source: Joel requested reuse of the impact-review framework with less ceremony, accepted the bounded two-pass plan, and directed “ok lets do pass 1.” That authorizes the selected approach and this implementation pass, not automatic acceptance of future decisions or permission to commit/push subsequent work.

## Evidence and consequences

[Working process](../workflow/README.md#decision-impact-assessment) and [criteria](README.md#when-a-record-is-needed) describe the contract. The existing ADR template and commands remain unchanged. Legacy receipts gain a pending assessment through --draft. Agent judgment still determines semantic impact; the checker catches missing/inconsistent/stale recording. A small whole-task reassessment can reopen after any nonhistorical edit, but unrelated documentation-group reviews remain valid.

## Acceptance and follow-up

J.L. accepted the approach and authorized Pass 1. Codex selected the field names, record-path validation and whole-change binding within that scope. Focused regression tests verify the implementation; five isolated Pass 2 trials exercised routine work, decision reuse, updates, proposals and an intentionally incorrect assessment. The trials support keeping the current scope without additional machinery. [Pass 1 evidence](../work/DECISION-IMPACT-PASS-1.md). [Pass 2 evidence and limits](../work/DECISION-IMPACT-PASS-2.md). J.L. authorized Pass 2 with “proceed to pass 2”; Codex performed the trials. This does not claim additional human acceptance of trial proposals. No new hook, remote CI job, scheduled task, agent or policy engine is introduced.
