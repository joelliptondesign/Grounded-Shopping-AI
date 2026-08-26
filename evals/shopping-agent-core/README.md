# Shopping Agent Core

Shopping Agent Core is the versioned behavior dataset for the grounded mattress-shopping system. [The evaluation framework](../../docs/EVALUATION.md) assigns its evidence to two independent responsibilities: deterministic [System Integrity](../../docs/evaluation/SYSTEM_INTEGRITY.md) and qualitative [Shopping Experience](../../docs/evaluation/SHOPPING_EXPERIENCE.md). It does not blend their results.

The suite is intentionally small and inspectable. Version `v1` contains 34 single-turn cases and 10 multi-turn journeys and remains unchanged with its historical runs. Version `v2` contains 12 single-turn cases and 7 multi-turn journeys (19 total). It revises the product contract around flexible budgets, directional preferences, near matches, restrained clarification, bounded conversational context, and customer voice.

## Files and case contract

- [`v1/single_turn.json`](v1/single_turn.json) contains extraction/state, decision, grounding-validator, presentation, and qualitative cases.
- [`v1/multi_turn.json`](v1/multi_turn.json) contains 10 journeys of 3–4 turns, with expected state after each turn.
- [`../runner.py`](../runner.py) validates cases, runs them, records configuration and raw outputs, and writes JSON plus Markdown artifacts.
- [`../scoring.py`](../scoring.py) owns exact checks, severity-aware summaries, supported metrics, and report rendering.
- [`v1/manual_scores.json`](v1/manual_scores.json) stores reviewed 0–3 conversation-quality scores and rationales. It starts empty by design.
- [`v2/single_turn.json`](v2/single_turn.json) and [`v2/multi_turn.json`](v2/multi_turn.json) cover all 30 semantic gold behaviors, merging related behaviors into maintainable journeys.

Every case declares a stable `case_id`, category, dimensions, failure severity, and slice tags. Cases may also name one or more critical invariants. Turn cases include shopper text, a deterministic fixture update, and gold intent/state/modality expectations. The runner resolves each declared state delta into the complete core gold shopper state after every turn and compares every field, so an omitted or accidentally reset field fails preservation checks without duplicating large state objects throughout the JSON. Decision cases start at structured state and pin exact eligibility, candidate, score/rank-signal, selection-authority, or block results. Grounding cases supply adversarial response fixtures to the existing validators.

The dataset and schema are independently versioned. Large catalog and review fixtures are referenced from `engine/data.py` and `engine/review_data.py`; only small purpose-built boundary catalogs are embedded in cases.

### v2 gold coverage

All 30 gold behaviors are represented. Closely related behaviors are merged as follows: 8–9 share the priority-change/explanation journey; 10–11 share reference and topic continuity; 12 and 18 share correction with partial information; 15–16 and 26–28 share natural acceptance, rejection, hardening, and firmness updates; 19–20 share catalog/review polarity; 23–24 share comparison and follow-up choice; 25 and 29 share priority loosening with off-topic state preservation. Behaviors 1–7, 13–14, 17, 21–22, and 30 retain focused cases. This yields 19 maintainable cases instead of 30 near-duplicates.

## Running evaluations

From the repository root:

```bash
python3 evals/runner.py --validate-only
python3 evals/runner.py --deterministic-only
python3 evals/runner.py --suite-version v1 --deterministic-only
```

The runner defaults to v2. Do not run the full live v2 suite until deterministic results and implementation behavior have been reviewed.

Run the fixed five-case live CX calibration separately:

```bash
python3 evals/shopping_experience_calibration.py --validate-only
python3 evals/shopping_experience_calibration.py --live
```

This path uses production Luna routing for the shopping journeys and the independent offline CX judge. It writes a separate `shopping-experience-calibration/v1` artifact and cannot select the remaining v2 cases.

Filtering remains deliberately simple:

```bash
python3 evals/runner.py --category grounding_reviews
python3 evals/runner.py --case grounding_wrong_winner_001
python3 evals/runner.py --live --case journey_reviews_001
```

Deterministic mode uses fixture-backed structured updates and runs the real state merger, routing, decision logic, grounding validators, recovery logic, and presentation builders. It is fast, repeatable, and makes no model calls.

Live mode requires `OPENAI_API_KEY`. It replaces fixture extraction in understanding and journey cases with the production model route, then generates final conversational prose for journey turns. The configured production routes remain `gpt-5.6-luna` with `none` effort for structured understanding and lightweight grounded generation, and `low` effort for conversational reasoning. Add `--cx-judge` to run the independent `gpt-5.6-sol` judge over customer-facing journeys without changing production routing.

A full live run can make roughly 45 extraction calls plus up to roughly 65 generation attempts, depending on deterministic response paths and grounding retries. Use a case or category filter for development, and avoid repeating a full live run casually.

## Outputs and failure inspection

Each run writes beneath `artifacts/evals/shopping-agent-core/<version>/`:

- timestamped raw JSON with inputs, state, model outputs when live, decision results, grounding evidence, presentation contracts, final responses, timings, usage data, exact failures, tags, and configuration;
- a timestamped Markdown report;
- an entry in the [evaluation run index](../../artifacts/evals/INDEX.md).

Run filenames use immutable UTC identities such as `2026-08-26_154719_run.json` and `2026-08-26_154719_report.md`. Existing runs are never overwritten.

Core reports preserve deterministic regression details. The five-case calibration report shows System Integrity and Shopping Experience separately, followed by exact chronological customer conversations, structured UI content, criterion rationales, and blank human-review fields. Pass rates describe these small regression sets only; they are not production benchmarks.

## Qualitative scoring

Conversation-quality cases carry the relevant criteria and prepare responses for human review. Add reviewed scores to `v1/manual_scores.json`:

```json
{
  "case_id": "quality_product_explanation_001",
  "score": 3,
  "rationale": "Connects the winner to cooling and budget priorities, states one useful tradeoff, and remains easy to scan."
}
```

Scores must be integers from 0 through 3 and include a short rationale. The runner reports an average only for cases actually present in the score file; it never assigns or fabricates an unreviewed qualitative score. The rubric's information-density standard allows useful multi-sentence and two-paragraph answers when each part adds decision value.

## Critical invariants

The suite surfaces these as zero-tolerance gates:

1. Never recommend an ineligible product.
2. Never silently relax a hard requirement.
3. Never present unknown service availability as known.
4. Never invent product facts.
5. Never invent review evidence.
6. Never let generated language replace or reorder the validated shopping selection.
7. Never lose the last valid shopper state because extraction failed.
8. Never treat missing evidence as false.

One invariant failure remains visible even if every non-critical case passes.
