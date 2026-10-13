# Repository explorer: Phase 1 specification

Date: October 7, 2026
Status: Proposed specification; Phase 1 planning authorized by Joel. No application implementation or Groundwork extraction is authorized by this document.

## Outcome and scope

Build a local, read-only way to understand this repository through its maintained documentation, source-linked system explanations, and actual rendered UI patterns. This repository is the pilot. Eventual Groundwork reuse is a direction to assess after the pilot, not a current installation or capability.

Phase 1 delivers this specification and a [proposed boundary decision](../decisions/DR-0006-repository-explorer.md). It does not install packages, modify the renderer, create a working shell, run Live turns, or change the managed Groundwork core.

## Experience and navigation

Use a persistent left sidebar with Overview, System, UI Gallery, and Documentation. Search sits above the navigation. The main area shows the selected content; a source panel opens on demand. Use stable page and node IDs for shareable local links. Browser back/forward restores selection. On narrow screens, navigation and source details become drawers; reading content remains primary.

| Section | Initial content | Primary action |
| --- | --- | --- |
| Overview | Purpose, major areas, Demo/Live distinction, prototype limits, snapshot details | Open the conversation map or a gallery pattern |
| System | Major-parts map and Live conversation flow; separate Demo explanation | Select a node to inspect responsibility and sources |
| UI Gallery | Recommendations, two-product comparison, suggested replies | Switch examples, inspect data and sources, reset |
| Documentation | Curated current documents grouped by subject | Read, search, and follow related links |

Overview derives its content from Project Context rather than maintaining another summary. Historical test results remain dated evidence, never a current health badge. The gallery initially uses the existing conversation surface; component-only cropping/extraction is deferred.

## Documentation inventory

Paths below are repository-relative. Each selected Markdown document has one canonical explorer page, even when linked from several sections.

| Subject | Sources |
| --- | --- |
| Project | `docs/PROJECT-STATE.md`, `README.md`, `docs/SOURCE-MAP.md` |
| Getting started | `docs/TECHNICAL_OVERVIEW.md` |
| Architecture | `docs/ARCHITECTURE.md`, `docs/AGENT-FLOW.md` |
| Frontend and API | `frontend/README.md`, `api/README.md` |
| Product governance | `GOVERNANCE.md` |
| Evaluation | `docs/EVALUATION.md`, `docs/evaluation/SYSTEM_INTEGRITY.md`, `docs/evaluation/SHOPPING_EXPERIENCE.md` |
| Working process | `docs/workflow/README.md`, `docs/workflow/ARCHITECTURE.md`, `docs/decisions/README.md`, accepted/current decision records linked by the index |

Do not index the whole repository. Exclude secrets, environment files, logs, caches, worktrees, runtime metadata, and historical artifacts from discovery. Historical frontend briefs and dated work reports may be opened through explicit links, with a historical/evidence label, but are excluded from default current search. Proposed decisions are visibly proposed, not current policy.

Markdown links resolve against the original source directory. Selected documents become explorer routes; other allowed text sources open in the source panel; permitted external links stay external. Missing or excluded destinations show an explanation. Render Mermaid diagrams, code blocks, tables, and anchors; treat document content as untrusted and do not execute embedded scripts or arbitrary HTML. Search initially covers selected document titles/headings/body, system node titles, and gallery labels. Full code search is deferred.

## System map contract

Start with curated relationships based on Architecture and Agent Flow. A node has a stable ID, label, responsibility source, implementation sources, related documents, and optional dated verification references. An edge has a source reference and relationship label. Do not call imports execution order or turn documented relationships into runtime-tested claims.

Initial Live nodes:

| Node | Implementation sources |
| --- | --- |
| Receive message and load session | `api/server.py`, `api/sessions.py` |
| Interpret shopper needs | `engine/preference_extraction.py` |
| Merge state and route | `engine/conversation.py`, `engine/response_strategy.py` |
| Eligibility, scoring, recovery | `engine/decision.py`, `engine/recovery.py` |
| Bounded product selection | `engine/shopping_selection.py` |
| Select presentation | `engine/presentation.py` |
| Generate and validate wording | `engine/conversational_response.py`, `engine/grounding.py` |
| Adapt and deliver | `api/blocks.py`, `api/turn_stream.py`, `api/server.py` |
| Render shopper interface | `frontend/Rufus Shopping Agent.dc.html` |

Branch recommendations through selection; factual/comparison paths may bypass it. This is an explanatory map, not a universal trace of every branch. Link synthetic catalog/review evidence as supporting nodes. Describe Demo as browser-owned scripted flows; never attach the Live engine path to Demo.

## Proposed explorer manifest

Proposed authored location: `docs/explorer/manifest.json`, created in implementation after review. This specification is the contract draft, not a finalized schema or active configuration.

- `version`: manifest format version.
- `pages`: stable ID, title, section, repository-relative source path, classification (`current`, `proposed`, `historical`, `verification`).
- `systemNodes`: stable ID, label, documentation reference/anchor, implementation references, related page IDs.
- `systemEdges`: node IDs, label, supporting source reference.
- `galleryEntries`: stable ID, label, renderer reference, adapter/contract references, named example IDs and data references.

Each source reference uses a path plus optional anchor or symbol. Resolve line numbers from the current snapshot, rather than authoring brittle line numbers. Validate path containment, existence, unique IDs, and cross-references. Fail visibly for required sources; allow optional evidence to be absent with a clear label. This manifest supplies navigation and relationships, not duplicated explanatory paragraphs. Do not repurpose `docs/documentation-map.json`, which owns change-impact routing.

Generated output lives separately from authored sources. Its metadata records HEAD revision, generation time, dirty status, and hashes of included sources. Dirty status alone is not complete snapshot identity. Refresh regenerates from current files. If included sources change after generation, show a stale-snapshot notice until refreshed; do not suggest Git timestamps establish semantic freshness. A local server or explicit refresh comparison is needed to detect changes while viewing a snapshot.

## Renderer cleanup design for Phase 2

Inspected seam: engine presentation -> `api/blocks.py` -> `{blocks, products}` -> frontend `registerProducts()` / `renderTurn()` -> `renderVals()` -> existing template. The single `Component` owns orchestration and pattern rendering; there are no standalone exported card/table components.

Proposed cleanup:

1. Extract block-to-view preparation into an authored helper accepting explicit blocks, registered products, feedback state, and interaction callbacks. Preserve the app's current data defaults through an app wrapper; preview validation must reject missing required data rather than borrow Demo defaults.
2. Keep product registration/decorative fixture merging explicit. Label commercial fixture data separately from decorative preview fields.
3. Add a preview adapter that registers example products and replaces blocks immediately, with reset of timers, transient state, and scroll reservation. Avoid `renderTurn()` timing for static previews.
4. Supply controlled callbacks for replies, cart, feedback, and see-more. Initially show the action within the preview without calling the shopping API or inventing new product results. Disable mode switching and free-text submission in the preview surface.
5. Load the existing document in a separate frame to isolate global CSS and per-example state. Define an explicit, origin-checked preview bridge in authored logic if needed; do not depend on private React instances or modify `support.js`/`image-slot.js`.

Standalone React extraction is unresolved and unnecessary for the first attempt. Do not copy template markup into separate gallery components. Preview enablement must be explicit and leave normal app startup and interactions unchanged. The current runtime loads React from a CDN and uses a remote font; no-model browsing is not a claim of fully offline operation.

## Initial examples

| Pattern | Named examples | Required input |
| --- | --- | --- |
| Recommendations | Three options; one option; longer explanation | Registered product IDs and complete view data; explicit role/why; explicit see-more treatment |
| Comparison | Ordinary rows; unknown value; long names | Two registered IDs, names, and explicit rows; no fallback to Demo specifications |
| Suggested replies | Three replies; long reply; no replies | Explicit label list and controlled selection callback |

Example fixtures are synthetic preview evidence. API adapter tests can inform their shape, but fixtures must have their own IDs/provenance and must not be represented as successful model-generated turns. “No replies” should render no pills rather than an empty placeholder. Reject invalid product references with a readable preview error.

## Acceptance and verification

Phase 1 is complete when navigation, source inventory, manifest shape, preview boundary, preserved behavior, and implementation gates are reviewable. Its completion does not prove renderer feasibility in a browser.

For subsequent phases:

- Trace product selection from a map node to its implementation and documentation.
- Distinguish Demo, Live, commercial synthetic evidence, and decorative fixtures.
- Inspect each gallery example's actual renderer, input, and contract.
- Navigate with keyboard and browser history; preserve readable diagrams and source details at narrow widths.
- Refresh after a document change; display missing references and stale snapshots honestly.
- Confirm preview reset and zero shopping API/model calls, including clicks on every preview action.
- Verify existing Demo behavior, scrolling, and offline adapter/engine checks after renderer changes. Scope any Live/browser model calls separately before running them.
- Complete repository documentation/decision-impact review; preserve historical evaluations and unrelated edits.

## Gates and recommendations

Joel has authorized this Phase 1 planning work. The proposed source contract and renderer boundary require review before dependent implementation. Codex recommends an explicit preview adapter, controlled interactions, and reuse of existing authored rendering; this is not yet Joel's acceptance of those design details.

VitePress remains a candidate, not a selected dependency. Evaluate Markdown compatibility, diagram rendering, source-link handling, framed previews, and local startup in Phase 3. Do not require a backend/model key for documentation. Groundwork extraction, commits, pushes, and publication remain separately scoped actions.

No change to Project Context capabilities is warranted until implementation exists. This document is the durable pilot plan; Groundwork's managed copy remains untouched.

## Phase 2 follow-through

Joel authorized Phase 2 execution on October 7. The renderer preparation boundary above is implemented locally; see the [Phase 2 report](PHASE-2-REPORT.md). The navigation manifest, shell technology and later phases remain proposed. Earlier planning-only status describes the Phase 1 deliverable, not the subsequent authorization.

## Phase 3 follow-through

Joel authorized Phase 3 on October 7. The curated manifest and local documentation shell are implemented; see the [Phase 3 report](PHASE-3-REPORT.md). Codex selected an authored shell and bounded Node snapshot server rather than VitePress; the rationale is recorded in DR-0006. System node/edge and gallery arrays remain empty for later phases.

## Phase 4 follow-through

Joel authorized Phase 4 on October 7. System nodes and relationships now support a source-linked part inspector, separate Demo view, required references and snapshot-derived symbol lines. See the [Phase 4 report](PHASE-4-REPORT.md). Gallery and Groundwork extraction remain deferred.

## Phase 5 follow-through

Joel authorized the next phase after Phase 4. The gallery now reuses the framed shopper renderer with named examples and controlled interactions. See the [Phase 5 report](PHASE-5-REPORT.md). Broad acceptance and extraction remain deferred.

## Phase 6 follow-through

Joel authorized the next phase after confirming the gallery works. The bounded acceptance pass and exploration-focused copy changes are recorded in the [Phase 6 report](PHASE-6-REPORT.md). Groundwork extraction remains a later phase.
