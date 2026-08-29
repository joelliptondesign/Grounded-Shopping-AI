# Grounded Conversational Shopping Demo

This repository demonstrates an open-ended conversational shopping experience over a bounded, fixture-backed mattress model. A shopper can describe needs in natural language, refine priorities across turns, compare products, ask catalog or review questions, and recover from combinations that have no valid match.

The prototype is a **shopping agent with trusted commerce tools**. Language models interpret shopper language, make a bounded shopping selection, and write customer-facing responses. Deterministic application code defines which products may safely be recommended, represents commerce evidence, calculates score signals and near-match tradeoffs, validates the selection contract, chooses presentation structure, and validates grounded claims. The deterministic layer defines what the agent may safely recommend; the shopping agent decides which safe options are most useful to show.

This is a technical prototype, not production commerce infrastructure. Its catalog, service eligibility, and customer-review evidence are local fixtures, and its supported decisions are limited to fields represented by the schemas and data in this repository.

Current repository snapshot:

- 48 synthetic catalog products and 48 corresponding synthetic review records, with intentionally incomplete optional fields
- 193 passing unit tests
- 26 Shopping Agent Core v2 cases: 12 single-turn cases, 7 multi-turn journeys, and 7 cold-start journeys
- latest deterministic Core v2 artifact: 25/26 passed, with one documented non-integrity comparison-winner expectation mismatch after the catalog expansion
- a Claude Design shopper interface with a scripted **Demo** mode and a **Live** mode backed by this engine, served with the FastAPI adapter in `api/`

## What the System Demonstrates

- Natural-language preference extraction into schema-constrained shopper state
- An explicit distinction between non-negotiable requirements, target preferences, directional preferences, and semantic priorities across chat turns
- Deterministic eligibility filtering plus an inspectable scorer used as decision support
- Strict `strong_recommendation` and `exploratory_shortlist` shopping-selection contracts
- Explicit routing for recommendations, comparisons, product questions, service questions, and off-topic turns
- Agent-resolved conversational references grounded by a four-item window of shopper-visible presentation identity and order
- Restrained clarification, extraction-failure recovery, immediate near matches for ordinary preferences, and explicit approval before a true hard requirement changes
- Grounded catalog, service, ranking, and fixture-backed review evidence with validation and safe fallbacks
- Adaptive presentation through conversation, recommendation cards, comparison tables, product details, recovery choices, structured elicitation contracts, and conversational suggested replies
- One Claude Design shopper interface with a scripted Demo mode and an engine-backed Live mode
- Customer-facing conversational generation plus optional developer/debug inspection
- Validation-buffered response streaming and turn-level latency instrumentation
- Explicit task-based model routing and a small, inspectable model-selection experiment

## Architecture

For a product-level explanation of how the conversational system works, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The customer-facing product surface is the Claude Design frontend in `frontend/`. In its **Live** mode a turn travels:

```text
Claude Design frontend
  -> FastAPI (api/server.py)
  -> the Python shopping-agent engine (engine/conversation.py)
  -> presentation adapter (api/blocks.py)
  -> the same Claude Design renderer
```

Streamlit is no longer in that path. `streamlit_app.py` remains as a legacy debug and development surface over the same engine.

The turn itself is implemented by `engine/conversation.py` and is identical for both surfaces:

```text
shopper message
  -> strict structured extraction
       intent
       product / review context
       hard-constraint updates
       soft-preference updates
       semantic-priority updates
       clarification or recovery response
  -> persistent shopper state for the current session
  -> explicit response strategy
       recommendation | comparison | product fact | service fact | off-topic
  -> clarification or recovery when required
  -> recommendation path only
       deterministic eligibility filtering
       deterministic preference-weighted score signals
  -> validated structured shopping-agent selection
  -> grounded evidence assembly
       catalog fixture | service fixture | validated selection | review fixture
  -> deterministic presentation selection
       conversation | recommendation cards | comparison table
       product detail | recovery choices
  -> structured UI can render from the completed presentation contract
  -> conversational generation streams into a validation buffer
  -> grounding validation, one stricter retry, then deterministic fallback
  -> only validated or deterministic-safe language streams to the shopper
```

### Shopper interface: Demo and Live

`frontend/` holds the Claude Design interface. Both of its modes use the same visual system; only the source of the response differs.

- **Demo** is the original scripted, fixture-backed experience. It runs entirely in the browser with no backend or key, and is the reliable presentation path.
- **Live** sends every turn to this engine through `api/`. Selection, ordering, eligibility, shopper state, grounded evidence, comparison rows, service availability, and recommendation rationale all come from the backend.

Switching modes clears the conversation and returns to the cold-start screen; the two never share conversational state.

The division of authority in Live mode is deliberate. The engine owns commerce truth: which products are selected, in what order, at what price, under which constraints, and why. The frontend owns customer-facing presentation, including a small fixture layer of decorative commerce metadata keyed by `sku_id` — product imagery, display rating, review count, Prime badge, delivery date, and an optional list price. The engine's catalog carries none of those, and they exist so a Live recommendation renders in the same card as a Demo one instead of degrading into a sparser layout. **They never travel to the backend and never influence eligibility, ranking, grounding, or any agent decision.**

Live interaction follows the Demo prototype's model rather than a reduced version of it: size and approximate budget are preferred cold-start basics but never hard gates, explicit browse intent bypasses them, recommendation categories keep their heading and their `see more` link — which draws further real backend candidates — comparisons use the comparison treatment, service and haul-away questions answer from real backend evidence, and every turn ends in continuation pills chosen from the live shopper state.

### Understanding and shopper state

`engine/preference_extraction.py` calls the OpenAI Responses API with a strict JSON Schema. It extracts one of five broad intents plus a concrete shopping action (`recommend_products`, `compare_products`, `choose_from_products`, `answer_product_question`, `answer_service_question`, `off_topic`, or `clarify_reference`), grounded product IDs, requested information source, hard constraints, soft targets, semantic priorities, recommendation readiness (`low`, `exploratory`, or `strong`), and clarification or recovery signals. Readiness is a semantic interaction cue, not a numeric confidence score. It does not answer factual questions or invent numeric ranking weights.

The merged shopper state persists across turns within one conversation session. Null update values leave prior values unchanged; explicit values replace them, including `false` when a shopper reverses a Boolean requirement. State is in memory only—there is no user account, database, or cross-session persistence. For the Live frontend, `api/sessions.py` holds that state per conversation in the API process; restarting the server ends every conversation, and the frontend simply starts a new one.

Recent conversation supplies linguistic meaning; a four-record `recent_presentations` window supplies the authoritative modality, product identity/order, and active product/service/review topic that the shopper actually saw. The same agent extraction call resolves ordinary pronouns, ordinals, comparisons, and topic switches from both inputs. Application code then resolves IDs through the catalog, rejects invalid or out-of-scope actions, retries once, and can recover an obvious comparison scope from the authoritative UI record. This is bounded session metadata, not long-term memory or retrieval.

The supported hard constraints are requested size, an explicitly absolute maximum price, latex exclusion, and explicitly mandatory California haul-away. Soft state covers preferred budget, optional upper flexibility, preferred haul-away, and numeric attribute targets. Directional state represents “more” or “less” without inventing a number; semantic priorities use `low`, `medium`, `high`, and `critical`. Ordinary “under $2,000” language is a target. Only language such as “I absolutely cannot spend more than $2,000” becomes a hard ceiling.

### Task-based model routing

`engine/model_config.py` maps known application tasks directly to three roles: structured understanding, conversational reasoning, and fast grounded generation. The application does not ask an LLM to choose a model. Shopping selection uses the existing conversational-reasoning route. Filtering, scoring, recovery proposals, selection validation, presentation selection, claim validation, and fixed guardrails remain deterministic paths.

All roles use the model-selection winner, `gpt-5.6-luna`; conversational reasoning uses low effort while extraction and lightweight generation use none. `SHOPPING_MODEL_STRUCTURED`, `SHOPPING_MODEL_CONVERSATION`, and `SHOPPING_MODEL_FAST` can override the defaults explicitly. Current model verification, quality bars, the controlled 16-case Luna-versus-Terra comparison, and the unchanged routing decision are documented in [Luna vs Terra model selection](docs/MODEL_BAKEOFF.md), with [structured results](artifacts/model-selection/luna-vs-terra/v1/2026-08-26_results.json).

### Eligibility and ranking

`engine/decision.py` is authoritative for recommendations. It filters the catalog before scoring, treating missing evidence for an active hard requirement as unknown and therefore unsafe for eligibility. A blocked result includes active constraints and per-product exclusion metadata.

Eligible products are scored deterministically on price, firmness, support, cooling, and motion isolation. Numeric targets use distance scoring, while directions such as higher cooling use monotonic scoring. Semantic priorities map to inspectable numeric overrides (`1` through `4`) and are normalized with the default weights. Soft budget and preferred-service deviations add deterministic near-match penalties and shopper-readable tradeoffs; an absolute maximum remains a hard gate. Ties are stable by product ID.

The previous decision is carried across recommendation turns so the system can expose rank movement when priorities change. Ranking narrows and describes strong candidates, supports diagnostics and fallback, and remains stable for deterministic evaluation. Rank #1 is no longer automatically the shopper-facing winner.

### Shopping selection

After eligibility and scoring, `engine/shopping_selection.py` gives Luna the current shopper state, bounded recent history, recently referenced products, all eligible fixture products, represented review evidence when relevant, and deterministic ranks/scores as non-authoritative signals. It returns a strict, compact contract containing a selection mode, optional primary product, ordered product IDs, and rationale tags.

`strong_recommendation` is used when meaningful preferences distinguish a primary choice. `exploratory_shortlist` is used when the available signal—such as a broad budget range alone—does not justify a winner. The latter still shows up to three differentiated options and makes progress without unnecessary clarification. Every selection is checked against the eligible set, hard requirements, represented facts, mode/primary consistency, and supported rationale tags. One stricter retry is allowed; otherwise deterministic scorer order provides the safe fallback.

A sole hard-safe candidate in an `ALLOW` result is normalized to a singular `strong_recommendation`. Budget rationale validation distinguishes sensible use of the stated range from mere cheapness: an inexpensive outlier may be a lower-price or value option without being labeled a good use of a much higher target.

The fixture catalog is small enough to supply all eligible products to this step. A production-scale commerce system would normally retrieve or narrow a large eligible catalog first.

### Intent routing, grounding, and recovery

`engine/conversation.py` routes each validated turn. Only `recommend` enters eligibility and ranking. `engine/response_strategy.py` resolves exact product names or IDs against the catalog and builds grounded catalog comparisons, product facts, review facts, or California haul-away facts. Unrepresented products, attributes, and services remain unknown rather than being inferred as false.

When extraction supplies a specific product-scoped attribute, that specific topic takes precedence over a generic intent label. This lightweight rule preserves follow-ups such as “What about Metro Cool Comfort?” after a California haul-away question while retaining the bounded conversation history and existing pronoun behavior.

Blocking ambiguity returns one focused clarification only when useful recommendation work cannot continue. Extraction or schema-validation failure preserves the last valid shopper state and skips the decision layer. When hard-safe products exist but none satisfy all ordinary targets, the decision layer returns the closest products immediately with calculated tradeoffs. When no product satisfies true hard requirements, recovery may propose a verified change, but never weakening latex safety; a hard-requirement proposal is applied only after explicit approval.

Cold-start preference elicitation optimizes for time to useful products. For a nearly empty mattress request, size and approximate budget are the default high-value basics and may be asked together in one concise turn. Once enough signal exists for an exploratory shortlist, products appear; the agent does not run a questionnaire before searching. An explicit request to browse bypasses additional ordinary cold-start clarification. Preference learning then continues progressively through reactions to the cards—for example, liking an option but asking for something cooler immediately updates state and refines the results.

Three interaction types remain separate. A structured elicitation is an optional `single_select` contract whose labeled options carry exact state patches; selecting one resumes deterministically without another interpretation call. Suggested replies are only conversational shortcuts and continue through ordinary language understanding. Free text always remains available, including as the fallback when a renderer cannot display structured controls. “Show me options” skips an optional pending elicitation and resumes exploratory shopping. The same renderer-independent recommendation contract already carries stable product IDs, names, fixture prices, match reasons, and tradeoffs, which is sufficient for a later text-only recommendation renderer without weakening catalog grounding.

The Live frontend renders a pending elicitation as its option pills; tapping one posts the option label, which the API matches back to the contract and resumes through the deterministic resolver rather than re-interpreting it with a model. Free text remains available throughout. The legacy Streamlit view still uses the typed-text fallback rather than dedicated choice controls.

For generated prose, `engine/grounding.py` defines represented evidence and validates high-risk claims such as validated-selection identity, price and score values, latex status, haul-away availability, review ratings/counts/themes, unsupported quotations, and implied live capabilities. Product identity may be supplied by validated recommendation cards delivered with the prose, so conversational framing need not duplicate card names; any product explicitly named or recommended in prose must still belong to the validated selection. Generation receives one stricter retry after a validation failure and then falls back to deterministic customer copy. Off-topic and extraction-failure responses are fixed guardrails.

### Adaptive presentation

`engine/presentation.py` deterministically selects a renderer-independent `TurnPresentation` contract after routing and authoritative results are available. The model may rewrite the short conversational framing but does not choose the modality, reorder products, change comparison rows, or alter recovery actions.

- Recommendation turns show up to three cards in validated shopping-agent order; exploratory mode does not imply a winner. Consequential match facts such as verified latex-free status are foregrounded in the singular recommendation and its card.
- Comparisons use a table whose first rows reflect active priorities and hard requirements, followed by represented fields that differ meaningfully.
- Broad questions about one resolved product use a product-detail view; narrow facts stay conversational.
- Grounded relaxation proposals use recovery choices that preserve the approval boundary.
- Optional cold-start basics use a distinct structured-elicitation payload; open-ended clarifications may still provide conversational suggested replies.

The Claude Design frontend renders every one of these through one shared visual system; see [frontend/README.md](frontend/README.md) for how each contract maps onto its blocks. The legacy Streamlit view renders the same contracts with basic controls, and offers optional developer details for shopper state, intent and strategy, presentation selection and sources, ranking metadata, recovery state, extraction errors, and grounding audits. Its separate **Advanced / Experiments** view retains the original A/B comparison between a baseline LLM response and the deterministic decision layer.

### Streaming and latency

Structured interpretation, state validation, routing, filtering, ranking, grounding, and presentation selection all complete before customer-facing generation begins. Extraction remains one atomic schema-constrained call; partial JSON never updates state or enters decision logic.

For generated conversational framing, model deltas are collected behind the existing grounding validator. No unvalidated model token ever reaches the shopper. This deliberate validation buffer prevents an unsupported claim from appearing and later being retracted. Fixed guardrails, model-unavailable responses, generation failures, and grounding failures use deterministic fallback copy rather than a generated stream.

The Live frontend uses that boundary for progressive delivery. `POST /api/session/{id}/turn/stream` sends Server-Sent Events at the points where a turn genuinely completes: `presentation` once the validated structured contract exists, `message` once the prose has passed grounding validation, and `complete` with the continuation pills. Cards and comparison tables can therefore render while generation is still running, and the loading state stays visible so the turn does not look finished early. The events carry finished, validated artifacts — this is staged delivery, not token streaming. A buffered `POST .../turn` endpoint runs the identical engine path and serves as the fallback.

Live loading treatment is a semantic decision, not a view of backend stages. Simple conversational turns — greetings, a missing size or budget, unclear input, a narrow product fact — use the lightweight dots. Genuine multi-step shopping work — a recommendation search, a refinement that rebuilds the shortlist, haul-away or delivery discovery — may use the multi-step progress treatment. That progress tree is a turn-level artifact: it appears at most once per shopper turn and is retired as soon as presentation or message content lands, so any later wait in the same turn shows dots. A new turn is eligible for a new tree.

Each turn carries reusable timing metadata for extraction, decision readiness, presentation readiness, generation time to first token, generation completion, first visible response, and total turn latency. Durations use a monotonic clock; developer-facing timestamps are UTC. These measurements support later buffered-versus-streamed evaluation but are not themselves a claim that total latency improved.

## Review Evidence

Review evidence is implemented as a separate, precomputed fixture in `engine/review_data.py`. It contains per-product average ratings, review counts, qualitative themes, common praise, and common complaints. Review questions are classified within the existing product-question or comparison intents, with a structured review topic such as cooling, firmness, motion isolation, durability, praise, or complaints.

Implemented behavior includes:

- General and topic-specific review questions
- Explicitly unknown responses for review topics not represented by the fixture
- Catalog facts and review themes preserved as different evidence sources, including cases where listed firmness and reported experience differ
- Review themes in recommendation evidence and cards when a supported high or critical priority makes them relevant
- Review rows in review-focused comparison tables
- Validation of generated review themes, ratings, counts, live-status claims, and invented quotations
- A conversational-response path that can generate a review-enriched recommendation explanation from supplied review evidence

Reviews never affect eligibility or deterministic scores/rank order. Represented review evidence may inform the shopping agent's choice among eligible candidates and may appear in grounded prose or cards. Direct review questions and review comparisons also use review-grounded conversational responses and presentation data.

Not implemented:

- Live Amazon or marketplace reviews
- Live review ingestion or production review APIs
- RAG, embeddings, vector databases, or semantic review retrieval
- Review-informed ranking

## Example Conversational Contract

For a turn with an explicit non-negotiable ceiling such as:

```text
I need a king, and $1,500 is my absolute maximum. Cooling is critical and motion isolation is important.
```

the extraction layer can produce the following state update (abbreviated):

```json
{
  "intent": "recommend",
  "hard_constraints": {"size": "king", "max_price": 1500},
  "soft_preferences": {"cooling_target": 9, "motion_isolation_target": 8},
  "priorities": {"cooling": "critical", "motion_isolation": "high"}
}
```

Application code filters and scores the fixture catalog, then a validated structured shopping selection drives a presentation contract shaped like the illustrative example below. Exact product choice and order can change as the fixture and agent judgment evolve.

```json
{
  "decision": "ALLOW",
  "selection_mode": "strong_recommendation",
  "primary_product_id": "S04",
  "agent_selected_product_ids": ["S04", "S16", "S15"],
  "presentation": {
    "modality": "recommendation_cards",
    "products": ["S04", "S16", "S15"]
  }
}
```

The exact card order comes from the validated shopping-selection contract. Deterministic scores and ranks remain available as inputs and diagnostics, but generated conversational prose cannot substitute or reorder products.

For lower-level use, `evaluate_decision` accepts an already structured preference dictionary:

```python
from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision

preferences = {
    "requested_size": "king",
    "max_price": 1500,
    "cooling_preference": 9,
    "motion_isolation_preference": 8,
    "priorities": {"cooling": "critical", "motion_isolation": "high"},
}

result = evaluate_decision(preferences, SKU_CATALOG)
print(result["selected_sku"])
```

## Fixtures and Verification Scenarios

Fixtures demonstrate and test representative behavior; they are not a whitelist of accepted chat messages. With an API key, the chat accepts open natural-language input within the supported mattress-shopping model.

- `fixtures/conversational_voice.json` contains seven qualitative conversations covering fuzzy preferences, a soft budget, priority changes, no-match recovery, a saved-constraint conflict, comparison, and unknown information.
- `fixtures/adaptive_modality.json` follows one stateful conversation from recommendation cards to comparison, a factual answer, and refined recommendation cards.
- `fixtures/review_conversations.json` covers general reviews, topic-specific evidence, catalog/review disagreement, and an unknown review topic.
- The **Advanced / Experiments** view retains three original A/B presets: cooling under budget, required California haul-away, and an intentionally tight cooling/budget scenario.
- The 193 unit tests also exercise schema validation, state merging, intent routing, hard gates, missing optional metadata, catalog and review coverage, weight changes, stable ranking, grounding failures, review isolation, approval/rejection, and presentation contracts.

## Running the Repository

The repository requires Python and the dependencies in `requirements.txt`:

```bash
python3 -m pip install -r requirements.txt
```

For live structured extraction and conversational generation, create a `.env` file in the repository root:

```bash
OPENAI_API_KEY=your_key_here
```

Run the shopper application — one process serves both the API and the frontend:

```bash
uvicorn api.server:app --reload --port 8000
open http://localhost:8000/
```

The three-dot menu switches between **Demo** and **Live**. Demo is the scripted, fixture-backed Claude Design experience and needs no key or backend. Live runs this engine, so it needs `OPENAI_API_KEY`; without one it reports that a new shopping conversation is temporarily unavailable, because its first step is model-based structured extraction, and it does not bypass that boundary. `LIVE_DEBUG=1` adds a small development-only per-turn diagnostic field.

Run the legacy Streamlit debug surface over the same engine:

```bash
streamlit run streamlit_app.py
```

Without `OPENAI_API_KEY`, Streamlit still starts and the deterministic path under **Advanced / Experiments** remains usable with local fallback prose.

Run the complete test suite (model calls are mocked):

```bash
python3 -m unittest discover -v
```

Run the versioned Shopping Agent Core eval suite:

```bash
python3 evals/runner.py --deterministic-only
python3 evals/runner.py --suite-version v1 --deterministic-only
python3 evals/runner.py --live --cx-judge
```

Run the separate fixed five-case Shopping Experience calibration (not the full live v2 suite):

```bash
python3 evals/shopping_experience_calibration.py --validate-only
python3 evals/shopping_experience_calibration.py --live
```

Run the six-journey focused live reference-continuity regression:

```bash
python3 evals/conversational_reference_continuity.py --validate-only
python3 evals/conversational_reference_continuity.py --live
```

See [Evaluation](docs/EVALUATION.md), [System Integrity](docs/evaluation/SYSTEM_INTEGRITY.md), and [Shopping Experience](docs/evaluation/SHOPPING_EXPERIENCE.md); then see [Shopping Agent Core](evals/shopping-agent-core/README.md) for the dataset contract and [Evaluation Runs](artifacts/evals/INDEX.md) for reports and raw results.

Run the fixture review scripts:

```bash
python3 scripts/review_conversation_fixtures.py
python3 scripts/review_evidence_fixtures.py
```

Run the deterministic streaming, timing, and failure smoke scenarios (the script retains its historical filename):

```bash
PYTHONPATH=. python3 scripts/phase4f_smoke.py
```

Run the Luna vs Terra model-selection experiment when `OPENAI_API_KEY` is set:

```bash
python3 scripts/model_bakeoff.py --model gpt-5.6-luna
python3 scripts/model_bakeoff.py --model gpt-5.6-terra
python3 scripts/model_bakeoff.py --finalize-review
```

`python3 app.py` remains a legacy command-line smoke entry point for the original A/B path. Its current hard-coded empty query is rejected by the scope guardrail.

## Repository Map

- `frontend/`: the Claude Design shopper interface — Demo and Live modes over one visual system, its runtime, product imagery, and presentation-only fixtures. See [frontend/README.md](frontend/README.md).
- `api/`: the FastAPI adapter that puts this engine behind Live mode — sessions, the presentation-to-block adapter, staged delivery, and static hosting of `frontend/`. See [api/README.md](api/README.md).
- `bench/`: latency measurement harnesses and the recorded findings behind the current routing choices. See [bench/README.md](bench/README.md).
- `streamlit_app.py`: legacy debug and development surface over the same engine, plus the original A/B experiment.
- `app.py`: legacy command-line A/B smoke entry point.
- `engine/preference_extraction.py`: strict extraction schema, model call, validation, state merge, and decision adapter.
- `engine/conversation.py`: turn orchestration, intent routing, recovery coordination, evidence assembly, and presentation handoff.
- `engine/decision.py`: hard-constraint filtering, semantic-priority weights, deterministic scoring, ranking signals, and structured candidate results.
- `engine/shopping_selection.py`: strict agent selection, deterministic validation, one retry, and scorer-order fallback.
- `engine/response_strategy.py`: grounded catalog, service, comparison, and review lookups.
- `engine/recovery.py`: deterministic no-match analysis, exact-product conflict handling, pending proposals, and approved state patches.
- `engine/grounding.py`: recommendation/review evidence contracts and generated-claim validation.
- `engine/timing.py`: reusable turn timestamps, monotonic duration metrics, and response-path metadata.
- `engine/model_config.py`: explicit task roles, current model defaults, reasoning settings, and environment overrides.
- `engine/conversational_response.py`: contextual generation, validation-buffered streaming, retry, and fallback.
- `engine/explanation_llm.py`: grounded recommendation explanation generation, validation, retry, and deterministic fallback.
- `engine/presentation.py`: deterministic modality selection and renderer-independent presentation contracts.
- `engine/customer_copy.py`: fixed guardrails and deterministic customer-safe fallbacks.
- `engine/data.py`: 48-product local mattress catalog with varied price, size, construction, performance, and service coverage.
- `engine/review_data.py`: precomputed review-evidence fixture and narrow retrieval interface.
- `engine/prompts.py` and `prompts/`: loader and versioned extraction, voice, explanation, baseline, and retry prompts.
- `fixtures/`: qualitative voice, adaptive-modality, review-conversation, and Luna-vs-Terra experiment fixtures.
- `evals/`: semantic, versioned evaluation suites plus the deterministic/live runner and scoring code.
- `artifacts/evals/`: immutable evaluation runs and their human-readable index.
- `artifacts/model-selection/`: versioned model-selection evidence, including Luna vs Terra.
- `scripts/`: deterministic fixture review utilities and the live Luna-vs-Terra experiment harness.
- `tests/`: extraction, decisions, routing, explanations, recovery, conversational response, presentation, reviews, and fixture checks.

## Intentional Scope Boundaries

This is open-ended conversation over a bounded shopping model. The shopper is not limited to exact fixture wording, but grounded knowledge is limited to the local catalog, California haul-away field, review fixture, supported product attributes, and extraction schema.

The catalog and customer-review evidence are synthetic local fixtures, not live commerce data. Optional fixture metadata is intentionally incomplete: `null` means unknown or unrepresented, never false or zero. Consequential requirements still require affirmative evidence, while missing ordinary preference evidence is omitted from compact cards and does not become a fabricated low score.

The repository does not provide live inventory, live pricing, live fulfillment, checkout, retailer integration, production catalog or review APIs, semantic search, learned ranking, durable shopper profiles, authentication, analytics, or production reliability controls. The baseline path is intentionally less governed for comparison; it should not be read as an endorsed production architecture.
