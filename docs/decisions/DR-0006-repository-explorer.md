# DR-0006 Repository explorer source and preview boundaries

Status: Accepted for Phases 2–6 scope; later phases remain proposed
Date: October 7, 2026
Decider: Joel Lipton (Phases 2–6 execution scope); Codex (implementation choices)
Scope: Grounded Shopping AI local explorer pilot; no upstream Groundwork change

## Context

Joel requested phased planning for a repo explorer and authorized Phase 1 on October 7. He permits targeted component cleanup as part of setup, while standalone React extraction remains undecided. The current frontend combines UI patterns and conversation orchestration in one Claude Design component. A second renderer or duplicated prose could drift from repository truth.

## Options and recommendation

- Documentation shell only: lowest effort, but cannot inspect actual UI examples.
- Copy patterns into a new component gallery: quick isolation, but creates competing rendering sources.
- Extract a standalone React library first: potentially reusable, but expands the cleanup scope before proving need.
- Reuse the current template with an explicit preview adapter and project-owned source manifest: Codex's recommendation. Adds a controlled boundary while preserving current rendering.

## Decision and rationale

Joel authorized Phase 2 execution on October 7 after the specification was delivered. The implemented boundary is: maintained Markdown owns explanation; code owns implementation; curated mappings own navigation; preview fixtures own named examples. Label each basis and generated snapshot identity. Reuse the actual renderer, isolate preview state and callbacks, and defer framework extraction. Groundwork reuse is assessed after pilot evidence.

## Evidence and consequences

See the [Phase 1 specification](../explorer/PHASE-1-SPEC.md), [frontend guidance](../../frontend/README.md), [API contract](../../api/README.md), and [source map](../SOURCE-MAP.md). Inspection found `renderTurn()`/`renderVals()` and the engine-to-block adapter, but no dedicated preview interface. At Phase 1 inspection, browser preview feasibility had not been established; the subsequent Phase 2 report records the actual browser evidence. Runtime CDN dependencies prevent claiming fully offline operation.

Application behavior, evidence boundaries, generated runtime files, and managed Groundwork core must be preserved. Phase 1 added planning records only; subsequent authorized implementation is documented in the phase reports.

## Acceptance and follow-up

Joel subsequently directed “proceed to phase 2.” This authorizes the renderer preparation boundary in that phase; it does not authorize the documentation shell, Groundwork extraction, commits or publication. Codex chose authored helpers and a framed same-origin bridge within that scope. See the [Phase 2 report](../explorer/PHASE-2-REPORT.md). No generated guidance is supplied by this record.

## Phase 3 shell implementation choice

Joel directed “ok go to phase 3” on October 7. Codex selected a small authored HTML/CSS/JS shell with markdown-it, strict Mermaid rendering, and a separate loopback Node server. VitePress was evaluated as a documentation-first alternative: it supports custom themes and data loading, so this is not a claim that it cannot meet the need. The chosen tradeoff avoids compiling repository Markdown as Vue components and makes source-relative links, bounded source inclusion, uncommitted-content snapshots, atomic refresh and freshness checks explicit. It introduces more shell maintenance than adopting a ready-made docs theme; reuse this limited implementation only if the pilot is useful. Dependencies are pinned with a project-local lockfile; no shopping framework migration occurs.

References: [VitePress capabilities](https://vitepress.dev/guide/what-is-vitepress), [markdown-it configuration](https://github.com/markdown-it/markdown-it), [Mermaid usage/security configuration](https://mermaid.js.org/config/usage.html). [Implementation and verification](../explorer/PHASE-3-REPORT.md). This is Codex's technical choice within Joel's authorized Phase 3, not a separate user selection of this technology. At the Phase 3 checkpoint, Phases 4–7 remained outside scope. Joel subsequently authorized Phase 4 below.

## Phase 4 execution

Joel directed “ok proceed to stage 4” on October 7. The existing source-linked system contract is implemented with selectable parts and documented relationships, a separate Demo view, and distinct synthetic engine evidence and decorative frontend fixtures. Responsibility excerpts derive from maintained Markdown; required anchors and sources are validated at snapshot generation. Codex chose a keyboard-accessible linked part list and relationship inspector rather than a free-pan canvas for this initial map. [Phase 4 report](../explorer/PHASE-4-REPORT.md) records evidence and limits. Phases 5–7 and publication remain deferred.

## Phase 5 execution

Joel directed “good for now, lets go to next phase” after Phase 4, authorizing the existing Phase 5 gallery scope. The gallery reuses the actual shopper renderer in a same-origin frame, the authored preview contract and synthetic named inputs; it does not duplicate pattern markup or extract React components. Exact snapshot-backed preview resource routes support this boundary without exposing arbitrary files or shopping endpoints. Existing runtime CDN/font dependencies remain; this is no-model previewing, not fully offline operation or a hostile-code sandbox. Codex implemented scaling for the fixed shopper surface on narrow screens. [Phase 5 report](../explorer/PHASE-5-REPORT.md) records evidence. Phases 6–7, commits and publication remain deferred.

### Local gallery runtime repair

Joel reported preview loading failure after Phase 5. Codex bundled the existing runtime versions and font into the explorer, using the supported resource map in served preview HTML. This preserves the actual renderer and avoids modifying the vendor export or normal shopper deployment. Gallery use no longer needs CDN/font access after installation. See the Phase 5 repair evidence.

## Phase 6 acceptance and explorer copy

Joel authorized the next phase after confirming the recovered preview works. He also requested copy for developers, PMs and designers exploring the repository, rather than prominent agent-facing cautions. Codex moved detailed fixture provenance into an optional About disclosure, added descriptions of what each example demonstrates, and kept source/input inspection available. System copy now guides exploration without repeating verification caveats. Actual source documents and metadata remain authoritative and inspectable.

[Phase 6 report](../explorer/PHASE-6-REPORT.md) records acceptance checks, observed limits and offline evidence. This implements the pilot boundary rather than changing product governance. Groundwork extraction, commits and publication remain separately scoped.


## System interaction update · October 23, 2026

Joel explicitly requested the Architecture Explorer’s top-down diagram and drawer interaction for Shopping’s System tab, then authorized implementation. This supersedes the Phase 4 list-and-inline-inspector choice for that tab. The outcome is helping a non-engineer follow the application flow and understand the relevant code. The manifest remains the owner of system nodes, edges and source mappings; no new diagram dependency or application execution path was introduced.

Codex implemented the main flow, explicit alternate routes and separate supporting evidence/assets with native links and CSS. Selecting a step opens a nonmodal right drawer; default routes have no selection. Close, Escape and empty canvas dismiss with an exit animation; reduced motion skips it. Focused source explanations resolve against inspected source text during snapshot creation and reject missing matches. Full source inspection opens a separate snapshot-backed source-reader tab. Live and Demo, synthetic engine evidence and presentation assets remain distinct. Tests and bounded desktop/mobile browser verification are separate from user acceptance; no deployment or publication is implied.

Joel subsequently specified the Joel Knowledge Explorer as the source of truth for styles, interactions and design-system values. Codex extracted its existing component CSS into a canonical shared file, without changing its visual definitions, and added explicit generated-copy synchronization with source hashes for Shopping. Shopping builds remain portable: they verify the checked-in copies and do not require the original local folder. Refreshing the copies is deliberate.
