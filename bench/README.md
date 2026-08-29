# Latency benchmarks

Measurement harnesses for the Live pipeline. All of them drive the real engine
and real model calls — there are no synthetic timings here.

Start the API first (`LIVE_DEBUG=1` exposes the per-stage timings these read):

```
LIVE_DEBUG=1 uvicorn api.server:app --port 8000
```

| Script | What it measures |
| --- | --- |
| `live_bench.py` | Per-stage latency across ten Live scenarios, p50/p90. `--runs N --only <scenario> --out file.json` |
| `model_call_bench.py` | One model call in isolation, across reasoning efforts, with validation pass rate and the selections produced |
| `compare.py` | Two `live_bench` artifacts side by side, by stage |
| `perceived.py` | When the shopper first sees useful grounded content, buffered vs streamed |
| `eval_summary.py` | Compact CX + integrity summary for a calibration run artifact |

Stage timings come from `engine.timing`, which the engine marks in place as it
works: `extraction_*`, `routing_completed_at`, `decision_evaluated_at`,
`selection_*`, `decision_ready_at`, `presentation_ready_at`, `generation_*`.

## Measured findings

Recorded so the conclusions can be re-checked rather than re-argued.

**Shopping selection is reasoning-bound, not context-bound.** The call sends
~8.3k input tokens and returns ~97 output tokens, yet takes 3.8 s p50 at
`reasoning=low`. At `reasoning=none` it is 1.5 s (−60%), but the calibration CX
average falls 2.8 → 2.2/2.4 across two runs, so the effort stays at `low`.
`model_call_bench.py` re-runs this comparison directly against the selection
prompt.

**Narrowing the candidate payload buys nothing.** Cutting 48 eligible candidates
to a diversity-preserving 12 (17 KB → 4.2 KB) produced no measurable latency
change, because input size is not the constraint. Rejected.

**The grounding retry rate is noisy, and publishing the evidence contract did
not reduce it.** A first attempt appeared to cut retries from 38% to 8%, but
both numbers came from 13-turn samples. Re-measured over 42 turns: 31% on the
unmodified build, 45% with the contract published in the payload, and 26% on the
unmodified build again. The metric varies around ~30% on identical code, and
there is no evidence the change helped, so it was reverted. Any future attempt
here needs a sample large enough to separate the effect from the variance.

Measuring this means driving several review-heavy journeys and counting turns
where the generation audit reports more than one attempt (`LIVE_DEBUG=1` exposes
it). Use at least 40 turns per build before drawing a conclusion.
