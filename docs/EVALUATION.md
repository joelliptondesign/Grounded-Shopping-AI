# Evaluation Framework

## Philosophy

The shopping experience is the product. Evaluation starts from conversational freedom and constrains behavior only where reliability requires it.

```text
SHOPPING EXPERIENCE
freedom / judgment / autonomy / helpfulness
                  |
                  | operates freely within
                  v
           TRUST BOUNDARIES
safety / grounding / factual integrity / true non-negotiables
```

The prototype uses two independent judges. It never blends their results into one score.

- [System Integrity](evaluation/SYSTEM_INTEGRITY.md) asks whether behavior stayed inside real trust boundaries. It is predominantly deterministic and can block a release.
- [Shopping Experience](evaluation/SHOPPING_EXPERIENCE.md) asks whether the interaction felt like excellent modern consumer shopping assistance. It uses criterion-level human or model judgment.

## Arbitration

System Integrity wins when a disagreement concerns safety, compatibility, a true non-negotiable, factual or evidence integrity, authoritative recommendation identity, or unsupported capability. A delightful response cannot excuse a latex-allergy violation, invented review claim, unverified service promise, or substituted winner.

Shopping Experience wins when the disagreement concerns ordinary shopping judgment outside those boundaries. Flexible budgets, fuzzy preferences, sensible inference, useful near matches, presentation choices, and clarification restraint should favor shopper progress rather than maximum constraint satisfaction.

Integrity does **not** mean maximizing constraints or clarification, minimizing inference, requiring approval for ordinary flexibility, or demanding exact internal-state agreement when no trust boundary is crossed. Its purpose is to make conversational freedom trustworthy.

No exact match is usually a normal shopping condition, not a system failure. The assistant should show useful near matches and explain ordinary tradeoffs while continuing to preserve genuine non-negotiables. Empty authoritative eligibility blocks a recommendation only when no product can cross the active trust boundary; it does not require procedural “constraint relaxation” language or approval rituals for soft preferences.

## Product decision rule

Trust-boundary failures are blocking. Among systems that remain inside the boundary, prefer the stronger customer experience. In short: **Integrity defines the boundary; CX optimizes everything inside it.** Integrity does not define every behavior while CX merely decorates the result.

## Datasets and reporting

[Shopping Agent Core](../evals/shopping-agent-core/README.md) contains versioned single- and multi-turn cases. Deterministic fixtures test state, decisions, grounding, presentation, recovery, and eight critical invariants. Live runs use the production model routes and preserve transcripts, structured shopper state, authoritative results, evidence, presentation contracts, validation audits, timing, and model-call metadata.

[Conversational Reference Continuity](../evals/conversational-reference-continuity/v1/journeys.json) is a separate six-journey focused live regression for cards→ordinal comparison, compare→pick, comparison attributes and ordinals, review pronouns, service-topic switches, and genuine ambiguity. It uses production Luna routing plus the independent Sol Shopping Experience judge and deterministic System Integrity assessment; it is intentionally not a rerun of the full Core v2 suite.

Reports show separate sections:

- **System Integrity:** pass/fail, applicable invariant outcomes, non-negotiable violations, grounding or factual issues, recommendation authority, and state integrity.
- **Shopping Experience:** overall 0–3 result, applicable criterion scores and rationales, and the largest customer-experience issue.

A high CX score never erases an integrity failure. A harmless representation mismatch does not automatically lower CX.

## Workflow

1. Validate the dataset and run deterministic tests.
2. Inspect System Integrity failures and stop on a real trust-boundary violation.
3. Run a deliberately small live slice before a full live suite.
4. Run the dedicated CX judge on the preserved shopper-facing journeys.
5. Calibrate model judgments against human review; never silently revise them to match gold behavior.
6. Expand live coverage only after the small slice is understood.

Useful commands:

```bash
python3 evals/runner.py --validate-only
python3 evals/runner.py --deterministic-only
python3 evals/shopping_experience_calibration.py --live
python3 evals/conversational_reference_continuity.py --live
python3 evals/runner.py --live --cx-judge
```

The calibration command runs exactly five representative v2 journeys. The final command runs the complete v2 suite with production Luna routing and the independent Sol judge for customer-facing journeys.

## Latest v2 evidence

The final immutable full run is [2026-08-26_191216](../artifacts/evals/shopping-agent-core/v2/2026-08-26_191216_report.md). System Integrity passed 19/19 with every critical invariant intact. Shopping Experience averaged 2.06/3 across 17 judged journeys (four scored 3, ten scored 2, and three scored 1). The semantic regression layer passed 12/19; seven major mismatches were recorded, including a broken compare-then-pick journey and several priority/state extraction mismatches.

The run also exposed one invalid deterministic expectation: the fuzzy-preference journey required an exact clarification string despite receiving semantically correct behavior and a 3/3 Sol score. The v2 definition now marks that wording as non-exact; the immutable run remains unchanged and transparently includes the original false failure. No post-run rerun was performed.
