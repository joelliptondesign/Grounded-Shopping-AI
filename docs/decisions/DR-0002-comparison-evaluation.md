# DR-0002: Evaluate comparison continuity against displayed products

Date: October 1, 2026
Status: Implemented within the authorized issue-fix task
Implementation decider: Codex. Joel authorized fixing the discovered issues; this is not a separate human acceptance of evaluation quality.

## Evidence and decision

The 48-product deterministic journey shows S22/S32 first. The old extraction fixtures still name Night Drift/CalmWave, and the engine repairs those references using presentation history. Requiring the earlier S04 winner contradicts the displayed comparison. Recommendation authority already belongs to the validated selection, not an unconditional gold SKU (GOVERNANCE.md).

Replace that fixed-winner assertion with checks against the preceding visible products: exact first-two comparison order, a nonempty unique selection within the comparison, a primary choice within that selection, and rendered cards matching it. Preserve the stale extraction names as a recovery test. Keep all earlier failure reports immutable. Do not change engine ranking, catalog facts, eligibility, or selection authority.

## Alternatives and limits

Changing S04 to S22 would freeze another catalog-specific result. Dropping the assertion without replacement would lose coverage. Restricting the fixture catalog would hide the current reference-repair behavior. The chosen criteria test continuity, with negative unit cases that prove wrong scope and missing choices fail.

These checks do not judge whether the selected mattress is the best choice. This fixture runs through deterministic selection fallback and includes incomplete attributes; live shopping judgment, explanation quality, latency and cost still need separate evaluation. See [current evaluation evidence](../EVALUATION.md#current-v2-evidence).
