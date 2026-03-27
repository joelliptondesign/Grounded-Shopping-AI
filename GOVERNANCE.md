# Governance Guardrails (Phase 2A)

## Scope Intent Filter

This demo is scoped to mattress recommendation intent only.

If a query is unrelated to mattress selection, the app returns:

`This demonstration is scoped to structured mattress recommendation scenarios. Please adjust your query accordingly.`

The guardrail uses case-insensitive keyword checks:
- `mattress`
- `sleep`
- `firmness`
- `cooling`
- `motion`
- `budget`
- `trial`
- `allergy`
- `latex`

## Preset Scenarios

The UI includes four preset scenarios for reproducible demonstration prompts. Presets populate an editable query field.

## Deterministic Latex Safety Constraint

If query text contains any of:
- `latex allergy`
- `allergic to latex`
- `must not contain latex`

Then deterministic selection excludes SKUs where `contains_latex == True` before scoring.

If no SKU remains after this constraint, the deterministic output is:

`No available SKU satisfies the latex constraint.`

When latex gating is triggered and a SKU is selected, explanation text includes:

`The selection excluded latex-containing products due to the stated allergy constraint.`
