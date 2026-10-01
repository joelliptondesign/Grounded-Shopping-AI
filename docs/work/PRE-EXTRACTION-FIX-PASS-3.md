# Pre-extraction fixes: Pass 3

October 1, 2026 · Eight combined workflow trials passed; bounded pre-extraction verification complete.

[Command evidence and timings](pre-extraction-fix3-results.json) · [Reproduction script](pre-extraction-fix3-trials.py). Run the script with Python from this machine; it reads the named Shopping AI source, creates disposable repositories and writes its result under /tmp. No source-project writes or live calls occur.

## Scenarios

| Trial | Observed outcome |
| --- | --- |
| Rationale edit through generation and review | Stale guidance failed, explicit generation repaired it, update assessment passed, repeat generation/draft retained the reviewed state. |
| Explicit successor | Merely adding a proposal did not activate it. Selecting the proposal failed. Selecting an accepted fixture successor generated its links; the old record retained superseded history. No real decision was changed. |
| Missing rationale | Generation failed without changing destinations. Independent file editing remained possible. Repair, generation and review completed. This demonstrates command scope, not independent-agent compliance. |
| Shopping v2 shape | Explicit migration preserved the exact original bytes and base, reset assessments, and completed the draft/review/check lifecycle. Repeated migration was a no-op. |
| Portfolio v2 shape | The missing decision assessment was added pending. Full lifecycle completed in a disposable shape fixture; the real portfolio installation was unchanged. |
| Partial generation write failure | A fault injected at the second destination reported AGENTS.md as already written. Check detected remaining stale output; rerunning generation repaired it and completion passed. |
| Concurrent receipt edit | An injected edit before replacement stopped migration. The concurrent contents and original backup were preserved. Restoring the fixture receipt and retrying completed successfully. |
| Two topics in one destination | Both generated sections and relative links remained valid, and the review completed. |

## Measurement and scope

50 command invocations produced their expected outcomes, including deliberate failures. Wall times: minimum 57.79 ms, median 92.46 ms, maximum 110.45 ms. These are bounded guidance-copy measurements, not full-repository or human review-time benchmarks. A rule change adds explicit generation before the existing review checkpoint; repeat generation causes no content churn.

Trials used maintained working guidance and the actual checker/modules, with temporary Git baselines. Migration fixtures represent the two known shapes and use the temporary base; they are not claims of having migrated the live portfolio or reproduced its entire application. Filesystem faults were injected only into disposable copies. Review explanations were supplied by this scripted test, not by an independent agent.

The first test-script run compared a compactly serialized receipt with the draft command's pretty-printed version. The script was corrected to use the canonical serialization before testing byte stability. This was a test-fixture issue, not a product fix; the successful full run is the linked evidence.

No runtime changes were required. The 43 checker and two offline-runner tests from Fix Pass 2 remain the unchanged implementation baseline and were not repeated in this documentation-only pass. The current live guidance check and documentation review were run after updating these records. No product behavior, browser flow, live model, CI or deployment was exercised.

## Remaining boundaries

Generated guidance covers registered sections, not arbitrary prose. Accepted metadata does not authenticate approval. A schema-valid but semantically wrong assessment still requires reviewer judgment. Guidance source changes conservatively reopen review groups through their shared dependency fingerprint. Partial writes are reported and recoverable by rerunning, not a multi-file atomic transaction. Independent cold-start adoption, long-term drift and review burden remain unmeasured.

## Continuation

The two pre-extraction fixes are ready to serve as the canonical extraction baseline. Return to Phase 2 of the larger plan: create the canonical Groundwork source from these current working files. It has not been created yet. Preserve the uncommitted changes and user-owned ignore edits. No commit or push is included in this pass.
