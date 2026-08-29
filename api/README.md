# Live-mode API

A thin adapter that puts the existing conversation engine behind the Claude
Design frontend's Live mode. It is not a second agent: every turn runs through
`engine.conversation.process_conversation_turn` and
`engine.conversational_response.generate_turn_response` exactly as
`streamlit_app.py` runs them. No eligibility, ranking, grounding, recovery or
shopper-state logic lives here.

```
frontend  →  api/server.py  →  engine (unchanged)  →  api/blocks.py  →  renderTurn()
```

## Running

```
pip install -r requirements.txt
uvicorn api.server:app --reload --port 8000
open http://localhost:8000/
```

`OPENAI_API_KEY` must be set (`.env` is loaded). The server also hosts
`frontend/` at `/app`, so the prototype is same-origin — one process, no CORS.
`streamlit run streamlit_app.py` still works as the legacy/debug surface.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/session` | Start a conversation. Returns `{"session_id": "..."}`. |
| `POST` | `/api/session/{id}/turn` | One turn, buffered. Body `{"message": "..."}`. Returns `{"blocks": [...], "products": [...]}`. |
| `POST` | `/api/session/{id}/turn/stream` | The same turn, progressively (SSE). What the frontend uses. |
| `POST` | `/api/session/{id}/more` | The prototype's per-category "see more". Body `{"category": "...", "shown": ["S28"]}`. |
| `DELETE` | `/api/session/{id}` | Drop a conversation. `204`, idempotent. |
| `GET` | `/api/health` | Liveness plus catalog size. |

`404` on a turn means the session is unknown or expired; the frontend creates a
new one and retries once. `422` is an empty or oversized message.

An engine failure or a missing API key returns `200` with the engine's own
customer-facing copy plus a non-null `error` field (`engine_failure`,
`model_unavailable`, `routing_failure`) — never a silent fallback and never a
switch to Demo. Transport failure is handled frontend-side.

## Sessions

In-memory only, no database. A session owns exactly what the Streamlit session
owns: `preference_state`, the message history, and `previous_decision_result`.
Restarting the server drops every conversation by design. Idle sessions expire
after four hours and the oldest are evicted past 64 live conversations. A
per-session lock serializes turns, since engine state is not re-entrant.

## Presentation → blocks

`engine.presentation.build_turn_presentation` already returns a deterministic,
renderer-independent contract. `api/blocks.py` only restates it:

| Engine modality | Frontend blocks |
| --- | --- |
| `conversation` | `text` (+ `suggest` for elicitation options or clarification replies) |
| `recommendation_cards` | `text` + `recs` + `suggest` |
| `comparison_table` | `text` + `compare` (block-supplied `names` and `rows`) |
| `product_detail` | `text` + `service` (reused as a label/value fact table) |
| `recovery_choices` | `text` + `suggest` (the relaxation options and "keep my requirements") |

`products` carries backend commerce truth only — `sku_id`, name, price. The
decorative commerce layer (imagery, star rating, review count, Prime badge,
delivery date, list price) is fixtured frontend-side by `sku_id` and merged into
the same Claude Design card, so a live recommendation renders identically to a
demo one. None of it crosses this boundary in either direction.

The engine's headline selection reason fills the card's role heading; the
remaining `why_it_matches` entries and the tradeoff become the explanation line
beneath the card. Markdown emphasis in the engine's prose is mapped onto the
renderer's own bold text part rather than reaching the shopper as asterisks.

## Progressive delivery

`/turn/stream` runs the identical engine path as `/turn` — `_run_turn` is shared
verbatim — and [`turn_stream.py`](turn_stream.py) splits the result at the one
boundary that already exists: the
structured presentation is validated and final when
`process_conversation_turn` returns, while the prose is written afterwards.

| Event | Carries |
| --- | --- |
| `presentation` | validated cards / comparison / details |
| `message` | the conversational response, after grounding validation |
| `complete` | continuation pills and `state_hint` |

No internal pipeline stage is exposed and no unvalidated token is emitted. The
blocks are built by `turn_to_blocks`, the same function the buffered endpoint
uses, so the two paths cannot drift — `tests/test_turn_stream.py` asserts the
streamed pieces reassemble into the buffered payload exactly.

`state_hint` reports which cold-start basics are still outstanding and whether
anything is on screen, so the frontend can choose its loading treatment from the
engine's own state rather than guessing.

## Haul-away and service discovery

A haul-away question is answered as a fact *and* treated as a service need,
mirroring the prototype's `runHaul()` flow. Routing turns on one distinction:

- **naming a product** — "Does CoreFlex Entry include haul-away?" — stays a
  narrow grounded fact about that product.
- **asking about the shortlist** — "Does either include haul-away?", "How do I
  get rid of my old mattress?" — is answered for every product on screen via
  `service_availability`, not just the first one.

When at least one shown product carries the service, the answer names which
ones and stops there; no replacement search runs. When none do,
`_service_discovery_turn` searches for alternatives: the shopper's size, budget,
priorities and hard constraints are carried over unchanged and the service
requirement is applied **for that search only**, so it never becomes a permanent
constraint they did not ask for. Already-shown products are excluded, ranking is
the engine's usual `evaluate_decision`, and selection is the deterministic path —
the alternatives are already ranked and the shopper is waiting on a service
answer, so no extra model call is spent.

The turn then renders as recommendation cards introduced by a bold
`Options with haul-away` heading, followed by the prototype's haul-away pills.
If the search finds nothing that keeps the shopper's requirements, the answer
says so rather than stopping at "no". Eligibility is described at the level the
catalog represents it — California, not an invented ZIP.

## "See more"

The prototype's recommendation categories each carry a `see more` link. In Live
mode it posts to `/more` with the tapped category and the SKUs already on
screen. No model call: the shopper's current decision result already holds every
eligible, ranked candidate for their state, so
[`more_like_this.py`](more_like_this.py) only reorders products the engine has
already admitted — by the dimension the category names, with the agent's own
ranking as the tiebreak — and rebuilds the cards through
`engine.presentation.build_turn_presentation`. Hard constraints, eligibility and
grounding are the engine's, untouched.

Two extra products, under a bold heading, with no further `see more` link on
them — matching `moreFor()` in the design source. The new SKUs are appended to
the shopper's `recent_presentations` rather than replacing them, so a later
"compare the first two" still resolves to the original pair.

## Continuation pills

[`suggestions.py`](suggestions.py) picks up to three from the live state: the
shopper's top priority becomes the question ("Which sleeps coolest?" when
cooling is critical), the budget becomes a concrete lower target, and reviews or
haul-away drop out once `recent_presentations` shows they have been covered. The
previous turn's set is avoided so the pills move with the conversation. When the
engine specified its own replies — elicitation options, recovery actions — those
win outright.

## Card copy

[`card_copy.py`](card_copy.py) reads the engine's reason labels ("High cooling:
8/10", "Higher-priced option") back into semantic facts and writes them as one
conversational sentence: *"Excellent cooling and motion isolation, though it's
$79 above the budget you had in mind."* Every clause traces to a reason or
tradeoff the engine produced; no schema label reaches the shopper. It also
assigns each card a distinct category heading in the prototype's wording ("Best
overall", "Also great for cooling", "Better value").

## Structured elicitation

The frontend seam only carries text, so a tapped suggestion arrives as a
message. When it is verbatim one of the pending elicitation's option labels (or
its skip label), `_elicitation_response` routes it through the engine's
deterministic `resolve_elicitation_response` path instead of re-extracting it
with a model. Anything else is ordinary free text — which the elicitation
already allows.

## Debugging

Off by default. `LIVE_DEBUG=1` adds a small `debug` field to each turn: intent,
strategy, modality, readiness, action validation, pipeline actions, decision and
latency. No reasoning traces, no full turn dumps.
