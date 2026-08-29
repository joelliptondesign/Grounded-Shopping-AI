# Governance Guardrails

## Authoritative Sources

Customer-facing claims follow an explicit source map:

- Product facts: the 48-product structured synthetic catalog fixture. Missing optional attributes remain unknown; they are not converted to false or zero.
- Service eligibility: the structured service fixture and eligibility logic. Model knowledge is never used for service answers.
- Recommendation eligibility: the deterministic decision result. Products outside the hard-safe eligible set cannot be recommended.
- Shopper-facing recommendation identity and order: the validated shopping-agent selection. Deterministic scores and ranks are decision-support signals and fallback inputs, not final recommendation authority.
- Conversational preferences: validated structured conversational state. Downstream code does not reconstruct hard constraints from raw conversation text.
- Customer experience: the 48-record precomputed synthetic review-evidence fixture. Topic coverage intentionally varies. It remains separate from catalog facts and is never an eligibility or ranking input.

Before recommendation prose is generated, `engine.grounding.build_recommendation_evidence` creates a narrow contract containing represented fields for the validated selection, verified or unknown fact status, verified service state, active weights, active hard constraints, and any structured approved relaxation. The full catalog is not sent to the response model.

Generated recommendation text is checked against that contract. Validation rejects a substituted or reordered selection, a recommendation from a blocked result, unverified or contradictory high-risk product/service facts, an unapproved hard-requirement change, unsupported review topics/counts/ratings, fake review quotations, and claims about live inventory, live pricing, live fulfillment, or live review analysis. One stricter rewrite is allowed. A second failure, unavailable model, generation error, or blocked result uses a deterministic local response assembled from represented facts.

Review evidence may be attached to eligible-candidate context before bounded shopping selection, or after catalog product resolution for direct questions and comparisons. It never changes eligibility or deterministic scores. Catalog and review perspectives are preserved independently when they differ. The fixture retrieval boundary supplies only the requested topic (or a bounded general summary); no embeddings, vector database, ingestion pipeline, semantic index, or production review API is implemented.

## Scope Intent Filter

This demo is scoped to mattress recommendations, comparisons, product questions,
and relevant delivery or service questions.

If a query is unrelated to mattress selection, the app returns:

`This demonstration is scoped to structured mattress recommendation scenarios. Please adjust your query accordingly.`

The legacy A/B form uses case-insensitive keyword checks:
- `mattress`
- `sleep`
- `firmness`
- `cooling`
- `motion`
- `budget`
- `trial`
- `allergy`
- `latex`

The chat path uses the schema-constrained turn intent. Normal shopping context such as sleeping hot, back pain, a partner disliking memory foam, or disliking a mattress's appearance stays in scope. Clearly unrelated requests receive one short scoped response and do not enter filtering or ranking.

Developer-only details expose the source map, grounding evidence, scorer leader,
validated shopping selection, verified and unknown facts, validation reasons,
retry/fallback state, and scope-guardrail result. These fields are hidden from the
customer transcript.

## Legacy Preset Scenarios

The secondary **Original A/B Experiment** includes three preset scenarios for reproducible demonstration prompts. Presets populate an editable query field; the primary **Shopping Agent** remains an open conversation.

## Deterministic Structured Constraints

The conversational extraction boundary represents requested size, explicit maximum price, latex exclusion, and required California haul-away as structured hard constraints.

The decision layer reads those structured fields directly and filters ineligible SKUs before preference-weighted scoring. It does not reconstruct recommendation constraints from raw query text. Raw text remains in use only for the separate scope/intent guardrail.

Ordinary targets such as preferred budget and preferred service produce safe near matches with explicit tradeoffs when useful. If no SKU remains after true hard requirements are applied, the structured blocked outcome includes the active constraints and per-SKU violation reasons for grounded recovery.

## Deterministic Soft-Priority Ranking

Semantic priorities (`low`, `medium`, `high`, and `critical`) are converted to numeric values (`1`, `2`, `3`, and `4`) only in application code. Explicit values override the corresponding default raw weight, then all active weights are normalized before scoring.

Unspecified dimensions retain raw weights that normalize to the scorer defaults: firmness `0.25`, support `0.35`, cooling `0.20`, motion isolation `0.20`, and price `0`. The raw defaults (`2.5`, `3.5`, `2`, `2`, and `0`) share the semantic priority scale, so `low` truly lowers a dimension and `critical` raises it. This preserves stable ranking behavior when the shopper has not expressed priorities.

Price priority affects only ranking utility. `max_price` remains a separate hard eligibility constraint, and `budget_target` remains a soft target. Changing priorities cannot admit a product excluded by a hard constraint.

Decision metadata exposes normalized weights, candidate scores, previous/current ranks, and the scorer leader for the optional developer view. The shopping agent receives those values as non-authoritative signals, selects within the eligible set, and returns a strict contract. Generated prose may describe supported rank movement, but it cannot replace or reorder the validated selection.
