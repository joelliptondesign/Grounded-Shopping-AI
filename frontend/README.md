# Rufus Shopping Agent — frontend

The Claude Design prototype, imported from
`claude.ai/design/p/73c048e7-3ab2-4c31-aabc-6fcb20f49073`.

`Rufus Shopping Agent.dc.html` is a Claude Design document: markup in `<x-dc>`
(driven by `sc-if` / `sc-for` / `{{ }}` holes) plus a `class Component extends
DCLogic` in the trailing `<script type="text/x-dc">`. `support.js` is the
runtime and `image-slot.js` the product-image element; both are vendored here.

Serve it over HTTP — the runtime fetches its imports, so `file://` will not
work. The API server in [`../api/`](../api/) hosts this directory at `/app`, so
one process covers both modes:

```
uvicorn api.server:app --reload --port 8000
open http://localhost:8000/
```

Demo mode alone needs no backend — any static server will do.

## Shopping mode

The three-dot menu in the header switches between two modes. `mode` defaults to
`"demo"`.

**Demo** is the original fixture-backed experience, unchanged: `classify()`,
`route()`, `readiness()`, `resolveRefs()`, the recommendation / comparison /
service / haul-away flows, and their scripted progress timing.

**Live** routes every submission through `submitLiveTurn(text)` and nothing
else — `route()` is never called. That call posts to the local API, which runs
the real Python conversation engine.

## The backend seam

`submitLiveTurn(text)` is the only path to the backend. It resolves to a *turn*:

```js
{
  blocks: [ /* the same block shapes the demo pushes */ ],
  products: [ /* backend products, registered into BY_ID */ ]
}
```

`renderTurn()` registers the products and pushes the blocks through the existing
renderer, so both modes share one UI. Block kinds: `user`, `text`
(`parts: [{ t, b }]`), `progress`, `dots`, `recs`, `compare`, `service`,
`suggest`, `feedback`.

Routing, ranking and copy decisions belong to the Python engine on the other
side of that call, not to `submitLiveTurn()`. See [`../api/README.md`](../api/README.md)
for the endpoints and the presentation-to-block mapping.

### Live interaction parity

Live mode uses the prototype's interaction model, not a reduced one:

- recommendation categories keep their heading and their `see more` link, which
  posts to `/api/session/{id}/more` and renders more real backend products
  through the same cards
- every recommendation, comparison and answer ends in continuation pills, chosen
  from the live shopper state
- `moreFor()` is shared; only the source of the extra products differs

### Progressive completion

Live turns use `/api/session/{id}/turn/stream`. `runLive()` renders the design's
progress timeline from real backend stages, drops in the validated cards or
comparison as soon as they arrive, keeps a single active progress line beneath
them so the turn never looks finished while prose is still being written, then
inserts the prose above the results and finishes with the pills. If the stream
fails it falls back to the buffered `submitLiveTurn()` seam.

Live pacing follows backend readiness: the 420 ms scripted beat before a turn is
Demo's, and Live uses 80 ms. Demo's timing is untouched and still matches the
design source exactly.

### Loading treatment

The prototype reserves the multi-step progress timeline for genuine multi-step
shopping work and answers everything else with dots. `liveLoading()` applies
that same rule before a turn starts:

| Turn | Treatment |
| --- | --- |
| greeting, unclear or malformed input, acknowledgement | dots |
| asking for a missing size or budget | dots |
| the answer that completes size + budget | progress — recommendation search |
| a shopping request with enough signal | progress — recommendation search |
| a new price or priority that rebuilds the shortlist | progress — refinement |
| haul-away, delivery or setup discovery | progress — service |
| a haul-away question naming one product | dots — it is a narrow fact |
| compare, product fact, review question, "see more" | dots |

"Are we still collecting the basics" is answered by `state_hint` on the previous
turn's response — the engine's own account of the shopper's state — rather than
guessed in the frontend. Backend pipeline stages are never mapped to the
timeline. Demo timing is untouched.

The tree is a **turn-level artifact**: at most one per user turn. It appears
once near the start and `treeConsumed` retires it the moment real content lands,
so every later pause in the same turn renders dots at the new end of the
conversation rather than a second tree. A new turn takes a fresh `pid` and is
eligible for a tree again.

### Progressive delivery

Live turns use `/api/session/{id}/turn/stream`. The validated structured result
is sent as soon as the engine returns it, while the prose is still being
written; the loading block carries on beneath the results so the turn never
looks finished early. The prose then lands above them and the pills close the
turn — the same block order the buffered payload produces, proven by
`tests/test_turn_stream.py`. If the stream fails before rendering anything, the
buffered `submitLiveTurn()` seam serves the turn instead.

Live pre-roll is 80 ms; Demo keeps its scripted 420 ms beat.

### Live sessions

The frontend creates a session lazily on the first live turn and holds the id.
Sessions live in the API server's memory, so a `404` (server restarted, session
expired) is handled by discarding the id, creating a new session and retrying
the turn once. Resetting the conversation or switching modes deletes the
server-side session and bumps `liveEpoch`, which discards the response of any
turn still in flight.

### Presentation fixtures

The Claude Design card is authoritative. The engine owns which products are
selected, their order, names, prices, attributes, rationale and tradeoffs — it
carries none of the decorative commerce chrome an Amazon card shows. Rather than
hide the rows that chrome fills, `LIVE_PRODUCT_PRESENTATION` fixtures it for all
48 backend SKUs, keyed by `sku_id`: photo, rating, review count, delivery
program and date, haul-away service window, Prime, and a `listBump`.

`registerProducts()` merges the two into the existing card view model:

```
backend truth (id, name, price)  +  presentation fixture (photo, rating, …)
                                 ↓
                    Claude Design card view model
```

These fields are presentation only. They never reach the API, never travel back
to the engine, and never influence ranking, filtering, grounding or any agent
decision. `listBump` is added to the engine's real price so the struck-through
"Typical" line stays consistent with real pricing; a third of SKUs have no list
price, as in the demo fixtures.

Seven product photographs cover 48 SKUs, assigned deterministically by catalog
position so a product always shows the same image.

The renderer itself is unmodified: every `sc-if`/`sc-for` block for user
messages, assistant text, progress, dots, recommendation cards, comparison
tables, service tables, suggested replies and feedback is byte-identical to the
design source. The only markup addition anywhere is the mode menu.

## Conversation state

Switching modes clears the conversation blocks, `ctx` (recent products,
comparison pair, subject, shopper preferences) and the busy flag, and returns
to the cold-start screen. `Reset conversation` does the same but keeps the
selected mode. The cart survives both.

Demo flows are chained `setTimeout` calls, so this script shadows `setTimeout`
to track them; a reset cancels whatever is still in flight rather than letting
the tail of a turn land in a fresh conversation.

Backend products are registered into `BY_ID` under their real `sku_id`. Demo
fixture ids are never overwritten (`FIXTURE_IDS`), and the Demo catalog is never
consulted for a live response.
