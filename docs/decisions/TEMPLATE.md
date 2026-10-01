# DR-NNNN Decision title

Status: Proposed
Date:
Decider:
Scope:

## Context

What problem or consequential ambiguity requires a choice?

## Options and recommendation

Record the meaningful alternatives and tradeoffs. Mark agent recommendations explicitly.

## Decision and rationale

Leave unresolved until the authorized decider chooses. Cite the decision source without copying entire conversations.

## Evidence and consequences

Link affected code or maintained guidance, expected effects, verification, and known limits. Record any task-specific exception separately from shared policy.

## Acceptance and follow-up

Who accepted what, when, and which follow-up remains? Link a successor if superseded.

## Optional structured source for generated guidance

Use this section only when this record will supply generated guidance. Ordinary prose records do not require JSON. Replace the example values with the actual decision, rename the file to match its ID (for example, `DR-0001-preserve-reading-position.md`), and remove these authoring instructions. Replace the top-level `Status: Proposed` line with the block below; do not maintain two independent current statuses.

The example is deliberately proposed. Set `status` to `accepted` only after actual acceptance is recorded above. Do not select a proposed record in the active guidance map.

<!-- groundwork:decision-summary:start -->
```json
{
  "version": 1,
  "id": "DR-0001",
  "title": "Preserve reading position",
  "status": "proposed",
  "summary": [
    "Keep the reader's position steady while an existing response grows."
  ],
  "rationale": "Keep the beginning of the response visible so the reader can follow it naturally."
}
```
<!-- groundwork:decision-summary:end -->

This block owns the concise rule, rationale and current decision status. Keep the full reasoning, alternatives, actual decider, acceptance evidence, implementation state and verification limits in the prose sections. Structured fields are not evidence of approval.

Required fields are `version`, `id`, `title`, `status`, `summary` and `rationale`. Supported statuses are `proposed`, `accepted`, `rejected`, `superseded` and `unresolved`. A superseded record also requires `supersededBy`, a repository-relative successor path. Active generated guidance requires an accepted record with no `supersededBy` value. Additional fields are rejected by the schema.

To use an accepted record, explicitly select it in the project's configured guidance map and add matching generated-section markers to each destination. Run `node scripts/sync-guidance.mjs --write`, inspect the diff, then `node scripts/sync-guidance.mjs --check`. Keep exactly one marked JSON block in each selected record. Generation copies the selected rule and rationale and links back to the full record; it does not infer approval or choose the newest ADR.

Schema locations: canonical source `core/groundwork/schemas/decision-summary-v1.schema.json`; installed project `.groundwork/core/groundwork/schemas/decision-summary-v1.schema.json`.
