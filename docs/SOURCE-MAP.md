# Source and documentation map

September 30, 2026 · Editing and retrieval guide, not a generated inventory.

| Area | Implementation or evidence | Maintained guidance |
| --- | --- | --- |
| Product purpose and public story | Current application and authored claims | README.md; README-PORTFOLIO.md |
| Current operational state | Active surfaces, known gaps, installation status | docs/PROJECT-STATE.md |
| Eligibility, scoring, recovery, evidence | engine/decision.py; engine/grounding.py; related engine modules | GOVERNANCE.md; docs/ARCHITECTURE.md |
| Conversation and structured preferences | engine/conversation.py; engine/preference_extraction.py | docs/ARCHITECTURE.md; relevant prompts |
| Bounded model selection and response | engine/shopping_selection.py; engine/conversational_response.py; prompts/ | GOVERNANCE.md; docs/MODEL_BAKEOFF.md; evaluation guidance |
| API, sessions, streaming, presentation mapping | api/; engine/presentation.py | api/README.md; frontend/README.md |
| Authored frontend UI and interactions | frontend/Rufus Shopping Agent.dc.html | frontend/README.md; frontend/CLAUDE.md, with approved user-message scrolling |
| Export runtime and image tooling | frontend/support.js; frontend/image-slot.js | frontend/README.md; preserve vendor/generated boundaries |
| Synthetic product, review, service evidence | fixtures/; relevant engine loaders | GOVERNANCE.md; evaluation definitions |
| Tests and behavioral evaluation | tests/; evals/ | docs/EVALUATION.md; docs/evaluation/; evals/README.md and suite README |
| Historical execution evidence | artifacts/evals/; artifacts/model-selection/ | artifacts/evals/INDEX.md; never rewrite immutable runs as current truth |
| Latency and model comparisons | bench/; scripts/model_bakeoff.py | bench/README.md; docs/MODEL_BAKEOFF.md |
| Local setup and dependencies | requirements.txt; requirements-dev.txt; pyproject.toml | docs/TECHNICAL_OVERVIEW.md |
| Hosting configuration | vercel.json and deployment-related files | docs/DEPLOYMENT.md; do not infer deployment authorization |
| Legacy interfaces | streamlit_app.py; app.py | docs/TECHNICAL_OVERVIEW.md; verify consumers before changes |
| Groundwork and maintenance | .groundwork/core/ (managed); .groundwork/config.json (project-owned); AGENTS.md; CLAUDE.md; docs/workflow/; docs/decisions/ | This map and docs/PROJECT-STATE.md |

## Reading order and conflicting sources

Start at Project Context and retrieve only the relevant owner documents. GOVERNANCE.md governs product evidence and trust boundaries, not coding-agent installation authority. README-PORTFOLIO.md is authored public narrative, not an operational status log.

frontend/docs/PRODUCT_BRIEF.md and the accompanying implementation, visual-reference, and scenario documents originate in the earlier design work. In particular, the product brief’s “do not integrate” direction predates the integrated Demo/Live implementation. Preserve useful design intent, but use frontend/README.md and api/README.md for current integration behavior. Do not silently ratify every historical instruction.

For current scrolling behavior and its approval, follow [DR-0001](decisions/DR-0001-scrolling-conflict.md). If another consequential conflict appears, record it and clarify intent rather than treating code or historical prose as automatic authority.

Exclude .kilo/worktrees, caches, virtual environments, environment files, telemetry/logs, and historical evaluation runs from routine context scans. Retrieve a specific historical result only when needed as evidence. This is retrieval guidance, not an instruction to delete or reclassify files.

## Change impact

Review descriptions whose meaning could change; file paths are an initial routing aid. A prompt edit may affect governance or evaluation expectations even when no Python file changes. A new result should retain source revision, definition version, and execution mode rather than overwrite old results. Assess Project Context once per coherent task. The initial automatic routing is in docs/documentation-map.json; scripts/check-docs.mjs enforces recorded coverage against changed contents. See docs/workflow/README.md for review commands and scripts/verify-offline.py for isolated offline checks. This prose map supplies ownership context; it is not itself enforcement.
