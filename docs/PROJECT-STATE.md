# Grounded Shopping AI project context

Updated October 7, 2026 · Local explorer pilot through Phase 6 · Prior application baseline revision d45eae6.

## Purpose and current product

A working conversational mattress-shopping prototype for exploring product design, agent behavior, grounding, and evaluation. It uses 48 synthetic catalog products and corresponding synthetic review evidence. It is not a retailer integration or checkout system. [Public product narrative](../README.md) · [Architecture](ARCHITECTURE.md).

The primary surface is the integrated Claude Design frontend served by FastAPI. Demo uses browser fixtures and scripted behavior. Live calls the Python conversation engine and models. Both share the renderer, but their execution paths and state are distinct. The original Streamlit interface remains a legacy/debug surface. [Frontend](../frontend/README.md) · [API](../api/README.md).

The engine owns structured preferences, eligibility, bounded product selection, evidence, recovery, and generated-response validation. Frontend photography, ratings, and other decorative commerce fields are presentation fixtures, not evidence for the engine. Sessions are held in server memory. [Product governance](../GOVERNANCE.md).

## Source and context boundaries

This repository is the implementation target. The separate Desktop Rufus Shopping Agent Prototype folder is an older export, not a synchronization authority. Earlier frontend briefs retain useful design intent but include obsolete pre-integration instructions. Read their historical context through the [source map](SOURCE-MAP.md); do not reverse the implemented integration.

Current scrolling behavior and approval are in [DR-0001](decisions/DR-0001-scrolling-conflict.md). Generated agent guidance reproduces its rule and rationale. [Browser verification and limits](work/SCROLLING-2026-10-01.md) remain separate evidence.

## Verification baseline and gaps

October 1 isolated verification passes 198 unit tests and 26/26 Core v2 deterministic cases, with all nine critical invariants passing. The previous compare-and-pick mismatch came from an obsolete fixed winner; the evaluation now checks that comparison and selection follow the products actually shown. Engine behavior is unchanged. This verifies reference continuity, not ranking quality; 11 qualitative cases remain unscored. [Evidence and definition change](EVALUATION.md#current-v2-evidence).

Historical live evaluation reports and benchmark results are preserved under artifacts and bench. The offline audit did not rerun them, measure current live latency/cost, or perform browser acceptance. The current 26-case definition has no full live rerun established by the maintained evaluation guide. [Evaluation scope and evidence](EVALUATION.md).

The two pair-specific Demo price differences now derive from the price fixture: Polar/Zenith $10 and AeroFlex/Therma $50. Both were verified in the Demo browser. [Fix report](work/FIXES-2026-10-01.md).

Dependencies use minimum versions rather than a tracked dependency lock. The browser smoke loaded the frontend runtime and covered a limited Demo journey; Live/browser integration, deployment state, hosting controls and broader browser acceptance were not verified. Setup instructions are in [Technical Overview](TECHNICAL_OVERVIEW.md).

## Groundwork status

Installed: shared agent entry points, this context, source/document ownership, a working/decision process, grouped documentation-impact checks, and an isolated offline verification runner. The October 1 decision-impact extension adds one assessment to the same receipt and commands, with record-link/work validation and stale-assessment detection. Pass 1 implementation and focused tests plus five isolated Pass 2 workflow trials are complete. [Trial results and overhead](work/DECISION-IMPACT-PASS-2.md) confirm record reuse and review freshness; semantic classification remains the reviewer’s responsibility. [Decision-impact scope](decisions/DR-0003-decision-impact-review.md). The installation preserved product behavior; subsequent scoped fixes correct Demo price copy and the obsolete evaluation criterion. Three bounded installation trials verified review routing, selective invalidation, and offline reporting. A Demo browser smoke covered clarification, recommendations, comparison, and budget refinement. [Pass 3 results and limits](work/PASS-3.md). Independent cold-start use remains unmeasured. [Commands and limits](workflow/README.md). No new hook, CI gate, nightly task, backend connection, deployment, or framework migration was added.

Pre-extraction Fix Pass 2 installs deterministic rule-and-rationale generation and receipt schema v3 with explicit migration. Missing metadata blocks the affected check, not independent authorized work. [Contracts](workflow/GROUNDWORK-CONTRACTS.md) and [implementation evidence](work/PRE-EXTRACTION-FIX-PASS-2.md). Eight isolated [Fix Pass 3 trials](work/PRE-EXTRACTION-FIX-PASS-3.md) passed, including supersession, both migration shapes and fault recovery. Canonical extraction and reviewed local adoption of Groundwork 0.1.0-rc.2 are complete. The pinned core and ownership manifest live under .groundwork; scripts remain stable entry points. Project configuration, decisions and offline verification remain local. Superseded modules are historical evidence under docs/history/pre-canonical-groundwork.

## Maintenance

Keep this overview short. Update capabilities, constraints, known gaps, and current installation status when they change. Put detailed behavior in its owning guide, decisions in the decision index, and execution evidence in test/evaluation records. Do not append a session-by-session log.

Current Groundwork version: **0.1.0-rc.4**, the fourth candidate for version 0.1.0. It adds daily closeout instructions; checker code and schema contracts are unchanged. Earlier update evidence remains historical.

## Repository explorer pilot

October 7: Phase 1 specification and Phase 2 renderer preparation are complete locally. Authored block preparation is shared with an explicit, same-origin framed preview adapter for synthetic examples; normal Demo/Live rendering remains shared. A verification harness covers cards, comparisons and replies. Phase 3 adds a local documentation shell with curated navigation/search, rendered diagrams, source panels and hash-based snapshot refresh. Phase 4 adds a source-linked system map with selectable parts, relationships, separate Demo and Live views, and distinct engine evidence and decorative fixtures. Phase 5 adds ten named synthetic gallery states through the existing renderer, with controlled preview actions, clear/reset and source/input inspection. Preview runtime packages and font are served locally after installation. Phase 6 verifies the core explorer journeys and refines the copy for repository exploration. Its report preserves remaining browser/accessibility limits; Groundwork extraction remains deferred. [Specification](explorer/PHASE-1-SPEC.md) · [Phase 2 verification and limits](explorer/PHASE-2-REPORT.md) · [Explorer setup](../explorer/README.md) · [Phase 3 verification](explorer/PHASE-3-REPORT.md) · [Phase 6 acceptance](explorer/PHASE-6-REPORT.md). Groundwork extraction and publication remain deferred.

## Daily closeout · October 12, 2026

Groundwork **0.1.0-rc.4** is installed locally. Say “let’s close out for the day” or `/closeout` by voice or typing. Follow [.groundwork closeout](../.groundwork/core/WORKFLOW.md#user-triggered-daily-closeout): maintain context, run relevant checks, review task-owned changes, commit and push to the existing agreed upstream, and deliver a chat SITREP. Joel explicitly authorized adopting this procedure in this project on October 12. No deployment, merge, force-push, native slash command or automatic hook is included.
