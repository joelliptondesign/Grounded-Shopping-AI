# Grounded Shopping AI project context

Updated October 1, 2026 · Post-installation fixes · Baseline application revision d45eae6.

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
