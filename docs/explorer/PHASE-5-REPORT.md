# Phase 5: real-renderer UI gallery

October 7, 2026 · Joel authorized the next phase after Phase 4. Implemented locally. No shopping engine or renderer changes, model calls, publication or Groundwork extraction.

## Delivered

Three patterns use the existing shopper document and shared block-to-view adapter: recommendations, comparisons and suggested replies. Ten named states include three/one recommendations, long rationale, ordinary/unknown/long-name comparisons, ordinary/long/empty replies, and a deliberate missing-product contract error. The original shopping surface is preserved rather than duplicated into gallery components.

Explicit synthetic products and blocks own each input. Commercial fields and decorative images/ratings are labeled preview fixtures, not engine evidence or model output. Source links expose the renderer, adapter, contract and authored JSON. Input inspection shows each selected payload. Stable entry/example routes support search, history and source-panel closing.

The frame accepts only same-origin parent loads and emits controlled events. Cart, see-more, replies and feedback are observable without conversation execution. Clear replaces the preview with empty data; reset restores the selected example. Example changes recreate the frame. Narrow displays scale the fixed shopper surface to fit.

Snapshot validation rejects missing/duplicate examples, invalid products and unexpected error fixtures. Required renderer/runtime sources and the one allowed local product image are snapshot-backed and hashed. Exact preview resource routes require explicit preview mode; the explorer provides no shopping session endpoint. The shell permits only same-origin frames. The preview retains named CDN/font dependencies and runtime inline/evaluation requirements, with local-only connections. Remote runtime bytes are outside snapshot identity.

## Verification

Seven explorer tests and four existing renderer tests pass. Tests cover gallery source inclusion, local image freshness, missing examples, unsupported renderer sources and invalid products, plus the existing API/bridge/reset guards. Bundle/snapshot build passes.

Browser verification loads all ten named states; confirms unknown values and no-reply emptiness; observes cart, see-more, reply and both feedback events; clears and resets; follows contract source and closes back to the same selection; navigates from search and browser history; and checks narrow layout without page overflow. The deliberate missing-product state renders a readable error. [Desktop](evidence/phase-5/desktop.png) · [Mobile](evidence/phase-5/mobile.png).

The local preview audit reports zero attempted shopping session requests during the bounded checks. Existing renderer guard tests verify preview API entry points cannot issue requests. This is not a complete network/security audit: existing CDN/font requests still occur. Isolated offline unit and Core v2 deterministic checks pass; [source evidence](evidence/phase-5/offline-summary.json). Later changes were gallery validation/docs refinements, not engine behavior. Documentation-impact review is completed against cumulative Phases 1–5 work, preserving unrelated root ignore edits.

## Limits

The preview is the complete existing conversation surface, not separately exported React components. Fixed-surface scaling reduces text size on mobile. The examples are authored fixtures, not API-generated or model-evaluated shopping turns. Remote runtime dependencies can prevent loading; the gallery reports a timeout. This trusted local preview is not a sandbox for hostile repository code. Broad acceptance, component extraction, upstream Groundwork reuse and publication remain later work.

## Preview loading repair

After Joel reported a slow/missing render, the explorer now bundles the existing React 18.3.1, ReactDOM 18.3.1 and Babel 7.29.0 versions, plus Nunito from a pinned font package. A served-preview-only resource map uses the existing runtime hook; the original shopper document and vendored runtime are unchanged. Its served font reference becomes a local font-face rule. Preview CSP no longer allows CDN/font origins. Reset now retries the frame when it has not started.

Eight explorer tests and the build pass. Browser verification confirms rendered cards, example switching and Reset; all observed frame script URLs are localhost and there are no external stylesheet links. The previous network-access limitation above describes the original Phase 5 checkpoint, before this repair. No live calls or engine changes.

## Startup and frame reuse repair

Joel reported continued startup failure in the existing browser tab. That tab stopped responding to browser controls; a fresh tab rendered the same long-reply example. This identifies a tab-specific failure during verification, not a proven general browser root cause. The old tab could not be reloaded or closed through the available browser controls. A working replacement preview was opened separately.

The gallery now preserves its mounted frame across example and pattern changes instead of restarting the runtime repeatedly. The authored preview bridge accepts a bounded, parent/origin-checked readiness ping; readiness can be repeated without inputs or shopping calls. Reset retries startup when necessary. Snapshot identity changes rebuild the frame. Browser checks confirm direct long-reply rendering, repeated recommendation/reply switches and reset in the fresh preview. Eight explorer tests, five renderer tests and the build pass; offline verification was rerun because authored preview bridge code changed. This repair does not establish why the original browser tab became unresponsive.

The rerun passes unit and deterministic evaluation suites; [startup-repair offline evidence](evidence/phase-5/startup-offline-summary.json).
