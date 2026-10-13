# Phase 2: renderer preparation

October 7, 2026 · Implemented locally under Joel's direction to proceed to Phase 2. No commit, publication, shell implementation or Groundwork extraction.

## Changes

- [Authored renderer helper](../../frontend/renderer.js) prepares view values with explicit products, feedback, callbacks and app defaults. The existing template still renders every pattern.
- [Preview contract](../../frontend/preview-contract.js) validates explicit example blocks and complete card view data. Missing IDs, comparison rows and reply lists produce errors instead of Demo fallback.
- [Frontend component](../../frontend/Rufus%20Shopping%20Agent.dc.html) owns a query-enabled preview adapter. It replaces examples immediately, resets transient state/products/timers/scroll space, and accepts messages only from the same-origin parent. Replies, cart, more and feedback emit controlled events; mode switching/submission and shopping API entry points are disabled. Preview input is read-only. Image editing pointer interaction is suppressed in preview only.
- [Verification harness](../../tests/frontend/preview-harness.html) loads synthetic card, comparison and reply examples through that bridge. It is development evidence, not the Phase 3 shell or Phase 5 gallery.

Normal app defaults, routing and existing pattern markup are preserved. Vendored runtime files and the Python engine/API are unchanged. No standalone React library was introduced.

## Verification

`node --test tests/frontend/renderer.test.cjs`: four tests pass. Checks cover pre-extraction view values for all block kinds, feedback toggling, invalid preview inputs, controlled callbacks/reset, guarded API paths, and parent/origin filtering. The baseline fixture was captured from d56e0ea before extraction and excludes function values.

Isolated offline runner: 198 unit tests pass; Core v2 deterministic cases 26/26 pass. [Snapshot hashes and exit results](evidence/phase-2/offline-summary.json). Reports/index were written only inside the temporary isolated copy. The final frontend-only test adjustment followed that snapshot; the four Node tests were rerun afterward. No engine or application changes followed the snapshot.

Browser checks in the local static server:

- Actual card and two-product comparison render; comparison includes an explicit Unknown value.
- Cart/see-more report events without adding products or mutating cart; reply click reports its label without running a conversation.
- Reset to empty replies removes the prior pattern. Invalid recommendation data shows a readable preview error.
- Reload after the read-only-input change confirms preview input is no longer editable.
- Normal Demo cold start, typed submission, recommendation cards and suggested comparison complete. Comparison shows the established Polar/Zenith $10 difference.
- Screenshot review confirms the existing pattern layout. [Comparison capture](evidence/phase-2/comparison.png).

Documentation-impact review is completed in the repository receipt. No Live turns, model calls, broad accessibility acceptance, production behavior, or full scrolling/reduced-motion acceptance were verified. The existing scrolling implementation was preserved. Browser Demo copy remains scripted; its response to the $1,500 input used the existing $550 script and is not evidence of preference interpretation.

## Next boundary

Renderer reuse is established for the initial three patterns. Phase 3 shell and manifest remain unimplemented and require the next phase's scope. Runtime CDN/font dependencies remain; no-model preview is not fully offline. The preview bridge is a development interface, not a hostile-content sandbox. Keyboard access to image editor controls has not been assessed.
