# Decision records

Keep significant choices and unresolved conflicts durable without recording every task.

| Record | Status | Decider |
| --- | --- | --- |
| [ADR / DR-0001 User-message scrolling](DR-0001-scrolling-conflict.md) | See authoritative record | J.L. |
| [DR-0002 Comparison evaluation](DR-0002-comparison-evaluation.md) | Implemented within authorized fixes | Codex |
| [DR-0003 Decision impact in the existing review](DR-0003-decision-impact-review.md) | Accepted approach; two-pass implementation verified | J.L. (approach), Codex (implementation) |
| [DR-0005 Canonical Groundwork adoption](DR-0005-canonical-groundwork.md) | Accepted direction; adopted locally | J.L. (direction), Codex (implementation) |
| [DR-0004 Generated guidance and receipt v3](DR-0004-generated-guidance-and-receipt-v3.md) | Accepted direction; Fix Pass 3 verified | J.L. (direction), Codex (implementation) |

For new records use the next available identifier and the [template](TEMPLATE.md). Suggested states: proposed, accepted, rejected, superseded, or unresolved. State who actually decided and what evidence supported the decision. An agent recommendation is not human acceptance. Superseding a decision preserves the previous rationale and links both records. Current summaries belong in Project Context and owner documentation.

## When a record is needed

Use the same criteria during planning/discovery and at task completion. Record a choice that:

- Establishes or changes durable product behavior.
- Resolves conflicting requirements or guidance.
- Changes an important boundary, authority, architecture, or evaluation criterion.
- Makes a consequential tradeoff that future work needs to understand.

Judge the meaning, not the number of files or lines. Routine fixes that restore an agreed requirement, cosmetic edits, and implementing an existing decision do not need a new record. If an existing record explains the choice, link it. Update unresolved/proposed records as decisions develop; preserve accepted rationale and use a successor record for a material reversal.

During planning or discovery, surface a consequential unresolved choice before dependent work and get any required decision from its authorized owner. At completion, reconcile what actually changed. These are two moments for the same assessment, not separate forms or a record for every turn.

Use the existing documentation-review receipt's decisionImpact field: none, existing, update, or create; a brief reason; reviewer; and record paths when applicable. See [the review commands and field rules](../workflow/README.md#decision-impact-assessment). A reviewed assessment can reference a proposed ADR; it checks recording, not permission to implement the proposal. The actual decider, approval source and status stay in the ADR. Never infer approval from a passing checker or a name typed into metadata.
