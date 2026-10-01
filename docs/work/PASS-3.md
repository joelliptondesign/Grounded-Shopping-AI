# Groundwork Pass 3 verification

September 30, 2026 · Bounded installation trials complete.

## Trial results

Three isolated Git copies of the working project exercised real source files. The application checkout was not changed. Each trial required a pending documentation review, accepted a completed review, preserved prior reviews when an unrelated area changed, and invalidated them after a relevant follow-up edit. None required a Project Context rewrite; each still required a short assessment.

| Trial | Review targets | Documentation disposition | Verification |
| --- | --- | --- | --- |
| Composer placeholder clarification | frontend/README.md | No impact | 193 unit tests pass; Core v2 remains 25/26 |
| Unknown-fact response wording | GOVERNANCE.md; docs/ARCHITECTURE.md | No impact to described behavior | 191/193 unit tests pass; two literal-copy assertions fail; Core v2 remains 25/26 |
| Additional unverified-fact regression | docs/EVALUATION.md | Updated to describe new test | 194 unit tests pass; Core v2 remains 25/26 |

The engine trial is a detected failure, not an accepted product change. The two failing tests assert “don't have reliable information”; the trial used “don’t have verified information.” We did not weaken the tests or change production copy. The result demonstrates that documentation review and software verification answer different questions. The initial trial coordinator expected every unit run to pass and stopped on these failures; its expectation was corrected to retain and report the deliberately changed behavior’s failures. No installed checker fix was necessary.

All three deterministic evaluations retained the same known major mismatch: compare-and-pick expected S04, actual S22. No baseline failure was suppressed. [Results](evidence/pass3/results.json) and per-trial patches, logs, and source hashes are in [the evidence folder](evidence/pass3/). The evaluation trial’s new untracked test is preserved separately as trial-test.py because an unstaged Git diff does not include it.

## Browser smoke review

Served the existing frontend statically on localhost and used Demo mode only. The browser loaded the runtime and rendered the UI. Keyboard submission of “I need a mattress” produced size/budget clarification. A queen/cooling/motion request under $550 produced three cards. The comparison suggestion rendered Polar/Zenith attributes. A later request closer to $450 produced CirroLoft at $429 and AeroFlex at $449 with tradeoff copy.

Confirmed a pre-existing Demo defect: the comparison table shows $519 and $529, while its verdict says $16 less. Product source was not edited. Custom scroll behavior remains present and its intended contract is still unresolved. A wait for a recommendation suggestion initially timed out; subsequent inspection showed it rendered. This is a limited interactive smoke review, not a timing benchmark or a stable automated end-to-end suite.

Live mode, backend streaming in the browser, cross-browser behavior, full accessibility, cart, failure/recovery journeys and broad responsive coverage were not exercised. Browser smoke completion is not full product acceptance.

## Context entry walkthrough

Read the installed entry points and followed their source/document routes. They identify the integrated implementation repository, Demo/Live distinction, ownership of engine versus presentation fixtures, offline commands, known evaluation failure, and the unresolved scrolling decision. All Markdown links in the entry/context/source/decision path resolve.

This was a document-based walkthrough by the continuing agent, not a fresh independent agent or colleague. Independent cold-start effectiveness and long-term maintenance overhead remain unmeasured. No old chats were required for the walkthrough.

## End state

Groundwork is locally installed and tested for this scope. No app code, prompts, fixtures, evaluation gold expectations, or historical product evaluation records changed in the main checkout. The existing .gitignore edit is preserved. No commit, push, live model call, deployment, hook, remote CI, or nightly automation occurred.

Next product work should explicitly scope the Demo price-copy defect, scrolling decision, or expected-winner mismatch if Joel chooses to address them. These are not automatic follow-up authorization. Keep the lightweight context and grouped review process; use the existing offline runner and report any nonzero suite result.
