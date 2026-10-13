# Phase 6: pilot acceptance and exploration copy

October 7, 2026 · Joel authorized the next phase after confirming the gallery works, and asked for user-friendly copy for developers, PMs and designers. Implemented locally; no publication or Groundwork extraction.

## Copy changes

The gallery explains what each example demonstrates: card layout, longer rationale, comparison attributes, wrapping replies and error/empty states. Its primary actions are View code, View rendering logic, View data contract, View examples and Inspect input. Detailed fixture provenance remains under About this example rather than filling the main page. Interactions display plain action labels instead of internal JSON. System copy guides users through the code and connected parts, with short Live/Demo descriptions. Original documents, source hashes and example provenance remain inspectable.

## Acceptance results

| Journey | Result |
| --- | --- |
| System part → implementation and related documentation | Passed, including keyboard activation and source-drawer Escape dismissal |
| Gallery examples | All ten states loaded through the reused actual renderer, including readable missing-product error |
| Preview actions | Cart, see-more, replies and both feedback actions report controlled events; clear/reset restore content |
| Source/input inspection and provenance | Source drawer preserves selection; input and About disclosures are available |
| Navigation and history | Search-to-gallery, browser back/forward, and stable selections passed |
| Documentation diagrams | Eight diagrams rendered in Conversation Flow |
| Keyboard | Enter activates links, Escape dismisses source drawer, skip link focuses reading area |
| Narrow layout | Gallery and System fit a 390 × 844 test viewport with no page overflow; mobile menu routes and closes |
| Freshness | A fixture-description change shows a stale notice; refresh loads it |
| Failed refresh | Temporarily invalid fixture JSON shows an error and preserves the last working snapshot; restored data refreshes successfully |
| Existing Demo | Typed recommendation and suggested comparison render; the initial user message remains near the top of the conversation viewport |

Temporary acceptance edits were restored. Demo still uses its existing scripted $550 narrative for a $1,500 input; this pass preserved it rather than claiming language interpretation. No Live turn or model call was run. The preview's attempted-shopping-session counter remains zero during the bounded gallery checks.

Automated checks pass: eight explorer tests, five renderer tests and bundle/snapshot build. The isolated offline runner passes the unit and Core v2 deterministic suites; [source evidence](evidence/phase-6/offline-summary.json). Later changes were copy, manifest labels and description validation, followed by explorer/renderer checks. Documentation review is completed against cumulative Phases 1–6 work; unrelated root ignore edits remain preserved.

[Gallery capture](evidence/phase-6/gallery.png) records the exploration-focused copy.

## Remaining limits and next gate

This is bounded functional acceptance, not a comprehensive accessibility, security or browser endurance certification. The earlier unresponsive browser tab remains an observed platform/session issue without a proven root cause; this pass uses the working replacement. The System section is still a parts-and-relationships inspector rather than a draggable interactive diagram. Gallery patterns remain in the full conversation surface, scaled on mobile, rather than standalone components. Preserved Demo fixtures and deterministic checks do not establish Live model quality.

Phase 7 is an extraction/reuse assessment for the separate Groundwork project. This report does not authorize upstream changes, commits, pushes or publication. The pilot can be used locally now.
