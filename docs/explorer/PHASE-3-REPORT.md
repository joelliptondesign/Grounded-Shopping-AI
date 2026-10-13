# Phase 3: local documentation shell

October 7, 2026 · Implemented locally after Joel directed proceeding to Phase 3. No commit, remote publication, shopping backend/model calls, system-map implementation, full gallery, or Groundwork extraction.

## Delivered

- [Separate local shell and setup](../../explorer/README.md), with persistent grouped navigation, current-document search, reading outline, mobile navigation, source panel and snapshot details.
- [Project-owned manifest](manifest.json): 21 curated pages. Empty system-node/edge and gallery arrays preserve the later-phase boundary.
- Existing Markdown is rendered with headings/anchors, tables, code blocks and strict Mermaid diagrams. Prose remains in its owning source documents. Original text and content hashes are inspectable.
- Local snapshots include permitted directly linked text sources and current working files. Hash comparison identifies included source changes; revision/dirty metadata identifies repository state. Refresh rebuilds atomically without editing repository sources; a failed refresh leaves the prior snapshot available.
- Historical and verification sources open only through explicit links and are labeled. Current search excludes those classifications and proposed pages. Missing/excluded links show a reason.
- Parser, diagrams and bundling dependencies are pinned and locked in the explorer directory. Generated bundles live in temporary directories; node_modules is ignored locally without altering existing root ignore rules.

## Technical choice

Codex selected a small authored shell and loopback Node server rather than VitePress, within the authorized Phase 3 scope. Both can support documentation; the selected approach makes bounded source inclusion, source-relative links and uncommitted-file freshness explicit, without compiling repository documents as executable components. It carries additional UI/server maintenance. [DR-0006 rationale](../decisions/DR-0006-repository-explorer.md).

Raw HTML is escaped, comments omitted only from the reading view, Mermaid configuration directives rejected, and sources are never executed. Hidden/secrets/environment paths, unsupported files, symlinks and traversal are excluded. The local server has exact Host/Origin checks and only serves its own resource routes. This is a scoped developer tool, not an adversarial filesystem sandbox.

## Verification

Automated: five explorer tests pass (manifest/source boundaries, escaping and rendering, link routing, symlinks/missing files, classifications and snapshot drift). Four existing renderer tests pass. The 43 documentation-checker regressions and two offline-runner regression tests pass after adding explorer document ownership routing. Bundle/snapshot build succeeds.

Browser checks confirm eight rendered diagrams in Conversation Flow, current-document search and search-result routing, implementation source text/hash, source panel close and Escape dismissal, back/forward routes (including an excluded-source link), Enter-key skip-to-content focus, heading links, narrow-screen navigation and readable content at 390 × 844. A source edit caused the stale notice; Refresh picked up the new setup section. Planned System content is labeled Phase 4, with its source button disabled. An excluded shared Groundwork link produces a readable unavailable-source explanation. [Desktop capture](evidence/phase-3/desktop.png) · [Mobile capture](evidence/phase-3/mobile.png).

Final isolated offline verification passes 198 unit tests and 26/26 Core v2 deterministic cases. [Source hashes/exit results](evidence/phase-3/offline-summary.json) identify that snapshot. Later edits were documentation and small shell routing fixes; the explorer tests/build were rerun afterward. The Python engine and shopper renderer are unchanged by Phase 3. Documentation-impact review passes at completion. No Live calls or writes to historical evaluation outputs occurred.

This report does not certify broad accessibility, hostile-content resilience, production hosting or Live shopping behavior. The mobile check covered navigation/reading, not every diagram/table at every breakpoint. Source panels retain original text rather than offering syntax-aware code navigation.

## Intentional limits

System and UI Gallery are clearly labeled as planned Phase 4/5 pages linking to current documentation. Source panels show original text, including auxiliary Markdown; auxiliary documents are not promoted into the main search/navigation. Only direct links from curated pages are included, so deeper links may require adding a page to the manifest. Binary image references appear as labeled text; this phase does not fetch document imagery. Search has no full-code index. Refresh updates source snapshots; changes to shell assets/server code require restarting the local server. Standalone build output is a build artifact, not a hosted static website.
