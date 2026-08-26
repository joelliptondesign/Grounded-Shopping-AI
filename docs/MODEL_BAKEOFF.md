# Luna vs Terra Model Selection

## Status

The controlled Luna-versus-Terra comparison completed on 2026-08-26. Both models ran the same 16 fixed cases with the same prompts, evidence, validators, quality bars, and reasoning settings. Both passed 16/16. Raw outputs, exact input context for the eight generated cases, API usage, measured latency, calculated cost, deterministic checks, rubric decisions, and case preferences are preserved in the [structured experiment results](../artifacts/model-selection/luna-vs-terra/v1/2026-08-26_results.json). Sol was not run, and production routing remains unchanged on Luna.

Run the live experiment from the repository root:

```bash
python3 scripts/model_bakeoff.py --model gpt-5.6-terra
python3 scripts/model_bakeoff.py --finalize-review
```

The optional repeatable `--model` filter prevents an unintended candidate from running. Generation is streamed for TTFT measurement, but output remains unavailable for scoring until the full response has passed the production grounding validator. Automated grounding checks and the existing 0–3 human rubric remain separate.

## Official OpenAI verification

Verified against official OpenAI documentation on 2026-08-26:

| Model | Intended tier | Responses API | Structured Outputs | Streaming | Reasoning efforts | Input / cached / output per 1M tokens |
| --- | --- | --- | --- | --- | --- | --- |
| `gpt-5.6-luna` | Cost-sensitive, high-volume | Yes | Yes | Yes | none, low, medium, high, xhigh, max | $0.20 / $0.02 / $1.20 |
| `gpt-5.6-terra` | Balanced intelligence and cost | Yes | Yes | Yes | none, low, medium, high, xhigh, max | $2.00 / $0.20 / $12.00 |
| `gpt-5.6-sol` | Frontier capability | Yes | Yes | Yes | none, low, medium, high, xhigh, max | $4.00 / $0.40 / $20.00 |

Sources: [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [model guidance](https://developers.openai.com/api/docs/guides/latest-model), [pricing](https://developers.openai.com/api/docs/pricing), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), and [streaming Responses](https://developers.openai.com/api/docs/guides/streaming-responses).

Luna and Terra are the model-selection candidates. Sol is documented for completeness but is not included: the experiment starts with the smallest plausible configuration and escalates only on an observed failure.

## Task classes and explicit routes

| Task class | Application work | Default model | Default reasoning |
| --- | --- | --- | --- |
| Structured understanding | intent, constraints, preferences, priorities, references, review topic/source, sparse updates, ambiguity | `gpt-5.6-luna` | none |
| Conversational reasoning | fuzzy clarification, contextual priority changes, nuanced recovery, recommendation tradeoffs | `gpt-5.6-luna` | low |
| Lightweight grounded generation | comparison framing, review summaries, facts, short product explanations | `gpt-5.6-luna` | none |
| Deterministic paths | guardrails, filtering, ranking, recovery proposals, presentation, validation and fallbacks | None | None |

These are the selected production configurations after the completed comparison. `engine/model_config.py` maps application-known task roles directly. It never asks a model to select another model.

Environment overrides:

- `SHOPPING_MODEL_STRUCTURED`
- `SHOPPING_MODEL_CONVERSATION`
- `SHOPPING_MODEL_FAST`

## Dataset and configurations

[`fixtures/luna_vs_terra.json`](../fixtures/luna_vs_terra.json) contains 16 cases: eight structured-understanding cases, four conversational-reasoning cases, and four lightweight-generation cases. It reuses scenarios from `fixtures/conversational_voice.json` and `fixtures/review_conversations.json` by reference rather than creating a parallel fixture framework.

The cases cover king-plus-latex extraction, soft and hard budgets, relative priorities, corrections with state preservation, ordinal product references, review-source/topic classification, blocking ambiguity, fuzzy clarification, a reasoned priority change, no-match recovery, catalog/review disagreement, comparison framing, a review summary, a grounded product explanation, and a represented service fact.

| Task | Small configuration | Balanced comparison |
| --- | --- | --- |
| Structured understanding | Luna / none | Terra / none |
| Conversational reasoning | Luna / low | Terra / low |
| Lightweight grounded generation | Luna / none | Terra / none |

## Quality bars

The bars were fixed before live results:

- Structured: every result schema-valid; no critical hard-constraint error; no state loss; all represented exact assertions correct. Losing the latex exclusion is disqualifying.
- Conversation: no grounding violation or critical/major behavioral failure; manual average at least 2.0/3 using `docs/EVALUATION.md`; useful forward progress; no internal terminology.
- Lightweight generation: no grounding or unsupported claim; concise and useful; manual average at least 2.0/3.

Correctness and grounding outrank conversation quality, which outranks latency, which outranks cost. The cheaper model wins when quality is materially equivalent.

## Results

| Task | Luna quality | Terra quality | Luna latency | Terra latency | Luna cost | Terra cost | Preferred |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Structured understanding | 8/8 exact | 8/8 exact | 3,194 ms mean total | 2,730 ms mean total | $0.00204084 | $0.02375100 | Luna |
| Conversational reasoning | 4/4 grounded; 3.0/3 mean | 4/4 grounded; 3.0/3 mean | 931 ms TTFT; 1,454 ms total | 962 ms TTFT; 1,694 ms total | $0.00108220 | $0.01082200 | Tie on quality; route Luna |
| Lightweight generation | 4/4 grounded; 2.5/3 mean | 4/4 grounded; 2.75/3 mean | 875 ms TTFT; 1,994 ms total | 996 ms TTFT; 2,107 ms total | $0.00206100 | $0.02025000 | Tie overall; route Luna |

Both models passed all 16 cases. Structured outputs were schema-valid and exact across intent, hard and soft constraints, priorities, corrections, sparse-state preservation, product references, review source/topic, and blocking ambiguity. All eight generated responses from each model passed identical grounding validation; neither model produced an unsupported catalog, service, review, selected-product, unknown-as-false, or live-capability claim.

### Performance

Generation “total” and validated-visible total are identical because the response is buffered until grounding validation completes. Structured extraction is not streamed, so TTFT is not available for that class.

| Task | Model | Mean TTFT | Median TTFT | Mean total | Median total | Total difference vs. Luna |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Structured understanding | Luna | N/A | N/A | 3,194 ms | 2,918 ms | — |
| Structured understanding | Terra | N/A | N/A | 2,730 ms | 2,504 ms | 464 ms faster (14.5%) |
| Conversational reasoning | Luna | 931 ms | 966 ms | 1,454 ms | 1,413 ms | — |
| Conversational reasoning | Terra | 962 ms | 905 ms | 1,694 ms | 1,670 ms | 240 ms slower (16.5%) |
| Lightweight generation | Luna | 875 ms | 832 ms | 1,994 ms | 1,877 ms | — |
| Lightweight generation | Terra | 996 ms | 997 ms | 2,107 ms | 2,092 ms | 114 ms slower (5.7%) |

Terra TTFT was 31 ms slower (3.3%) for conversation and 121 ms slower (13.8%) for lightweight generation. The samples are small—four generated cases per class—so these are experiment measurements, not general service-level estimates.

### Token usage and cost

| Model | Input tokens | Cached input | Output tokens | Approx. total cost |
| --- | ---: | ---: | ---: | ---: |
| Luna | 27,788 | 13,722 | 1,747 | $0.00518404 |
| Terra | 27,788 | 11,865 | 1,717 | $0.05482300 |

Terra cost **10.58× Luna** for this experiment. Terra emitted 30 fewer output tokens overall (1.7% fewer), including 30 fewer across the generated cases (443 versus 473), so the cost increase came from model pricing rather than greater verbosity. Costs use API-reported tokens and the documented $0.20/$0.02/$1.20 Luna and $2.00/$0.20/$12.00 Terra rates per million input/cached/output tokens.

### Validator behavior

The earlier Luna run exposed two false positives: the review validator treated “Metro Cool Comfort” as an unsupported cooling theme in a firmness-only answer, and the general validator failed to recognize numeric catalog prices when checking rendered currency and their exact difference. Those fixes and regression tests were already in place for this comparison. The unchanged Luna raw outputs revalidated successfully, all Terra outputs passed, and Terra exposed no new validator defect.

## Side-by-side qualitative review

The existing harness had no blind-review facility, so this was a non-blind side-by-side review using the same 0–3 rubric in `docs/EVALUATION.md`; no infrastructure was added solely for blinding. Exact serialized input context and both raw outputs are also stored per case in the artifact.

### Fuzzy preference

Shopper/context: “I just don't want something that feels like my current mattress.” The assistant needed a focused clarification that helps the shopper name the disliked feel.

**Luna:** “What feels wrong about your current mattress—too much sinking, difficult to move on, too warm, too firm, or something else?”

**Terra:** “What feels wrong about your current mattress—does it sink too much, feel hard to move on, sleep too warm, feel too firm, or something else?”

Evaluation: Luna 3/3; Terra 3/3; both grounded. **Tie.** The questions create equivalent forward progress and shopper effort.

### Priority change

Shopper/context: “Actually motion isolation matters more. My wife moves around constantly.” Saved priorities made motion isolation critical and cooling secondary.

**Luna:** “Understood—motion isolation is now your top priority, with cooling as a secondary consideration. I’ll focus on mattresses that help keep your wife’s movement from disturbing you.”

**Terra:** “Got it—I'll make motion isolation the top priority to help minimize disruptions from your wife’s movement, with cooling as a secondary preference.”

Evaluation: Luna 3/3; Terra 3/3; both grounded. **Tie.** Both acknowledge why the priority changed and explain the same practical consequence.

### No exact match

Shopper/context: king size, California haul-away, and a firm $900 ceiling; the represented closest option preserving the other requirements costs $1,349.

**Luna:** “I’m not finding a king mattress that includes California haul-away within your absolute $900 limit. The closest option that keeps the other requirements is $1,349. Would you like me to show it, or keep the $900 limit?”

**Terra:** “I’m not finding a king mattress with California haul-away at your firm $900 maximum. The closest option that keeps those other requirements is $1,349. Would you like to see it, or keep the $900 limit?”

Evaluation: Luna 3/3; Terra 3/3; both grounded. **Tie.** Neither silently relaxes the ceiling, and both offer the same grounded next step.

### Catalog and review disagreement

Shopper/context: owner firmness experience for Metro Cool Comfort; review evidence says medium-firm with some “firmer than expected” feedback, while catalog firmness is 6/10.

**Luna:** “Owners generally describe the Metro Cool Comfort as **medium-firm**, though some find it **firmer than expected**. Its listed firmness is **6/10**.”

**Terra:** “Owners most often describe Metro Cool Comfort as medium-firm, though feedback is mixed: some say it feels firmer than they expected. Its listed firmness is 6 out of 10.”

Evaluation: Luna 3/3; Terra 3/3; both grounded. **Tie.** Both keep catalog and owner evidence distinct; Terra's extra wording does not improve the decision.

### Comparison framing

Shopper/context: compare Metro Cool Comfort ($1,099) with Urban Rest Core ($950), with cooling high priority and price medium priority; represented differences also cover ratings, construction, trial, and warranty.

**Luna raw output:**

> Here’s the practical difference between them:
>
> | | Metro Cool Comfort | Urban Rest Core |
> |---|---:|---:|
> | Price | $1,099 | $950 |
> | Cooling | 7/10 | 6/10 |
> | Motion isolation | 7/10 | 6/10 |
> | Firmness | 6/10 | 6/10 |
> | Support | 6/10 | 6/10 |
>
> Both are medium-firm hybrids with the same support and a 90-night trial plus 8-year warranty. Since cooling is a high priority for you, **Metro Cool Comfort** offers the stronger fit, while **Urban Rest Core** saves $149 if value is more important.

**Terra raw output:**

> Both are medium-feel hybrids with the same support level, 90-night trial, and 8-year warranty. The main differences are:
>
> - **Metro Cool Comfort** — $1,099; stronger cooling and motion isolation, with foam and micro-coils.
> - **Urban Rest Core** — $950; a more budget-friendly foam-forward hybrid, with slightly less cooling and motion isolation.
>
> Since cooling is a high priority for you, **Metro Cool Comfort** is the better fit if the extra $149 is within your budget. If keeping the price lower matters more, Urban Rest Core still offers a similar firmness and support profile.

Evaluation: Luna 3/3; Terra 3/3; both grounded. **Prefer Luna.** Its compact table makes the represented values and $149 tradeoff faster to scan.

### Review summary

Shopper/context: “Do owners think Metro Cool Comfort sleeps hot?” Review evidence says owners frequently report it sleeps cooler than traditional memory foam.

**Luna:** “Yes. Owners frequently describe the Metro Cool Comfort as sleeping cooler than traditional memory foam. Its listed cooling rating is 7/10.”

**Terra:** “Owners generally don’t describe Metro Cool Comfort as sleeping hot. Reviews frequently say it sleeps cooler than traditional memory foam, with a strong positive theme around cooling.”

Evaluation: Luna 2/3; Terra 3/3; both grounded. **Prefer Terra.** Terra answers the polarity of the shopper's question directly; Luna's opening “Yes” is ambiguous even though the evidence that follows is correct.

### Product explanation

Shopper/context: explain why selected AeroFlex Medium may fit queen size, $1,500 maximum, latex exclusion, and critical cooling preference using only represented recommendation evidence.

**Luna:** “AeroFlex Medium may work well for you because it matches your key requirements: it’s available in queen, costs $999, and doesn’t contain latex. Its cooling rating of 8 is also a strong fit for your very high cooling priority, thanks to its breathable foam core and transition coils.

It also offers medium firmness, moderate support, and good motion isolation, so it’s a balanced choice rather than an especially firm or highly specialized mattress. You’ll also have a 90-night trial and an 8-year warranty to give it a fair test.”

**Terra:** “AeroFlex Medium could work well for you because it meets your key requirements: it’s available in queen, costs $999—well within your $1,500 limit—and contains no latex.

Since cooling is especially important to you, its breathable foam core and transition-coil design offer strong cooling performance. Its medium feel should provide a balanced, adaptable surface, with solid support and good motion isolation. You’d also have a 90-night trial and an 8-year warranty.”

Evaluation: Luna 2/3; Terra 2/3; both grounded. **Tie.** Terra is modestly shorter (100 versus 116 output tokens), but both still add secondary details beyond the core fit explanation. This weakness is better addressed by tightening the Luna prompt than by paying for Terra.

### Service fact

Shopper/context: “Does Polar Motion Elite include haul-away in California?” Represented service evidence is positive.

**Luna:** “Yes. Polar Motion Elite includes haul-away in California.”

**Terra:** “Yes—haul-away is available in California for the Polar Motion Elite.”

Evaluation: Luna 3/3; Terra 3/3; both grounded. **Tie.** Both answer directly without unsupported service details.

Qualitative preference counts: **Luna preferred 1; Terra preferred 1; tie 6.** Terra's generated responses averaged fewer output tokens, but it did not solve the overlong product-explanation case and did not improve the already-perfect conversational rubric average.

## Task-level recommendation

| Task class | Luna | Terra | Recommended | Why |
| --- | --- | --- | --- | --- |
| Structured understanding | 8/8 exact; $0.00204084 | 8/8 exact; 14.5% faster; $0.02375100 | Luna / none | No quality difference; Terra's one-run latency advantage does not justify 11.64× class cost |
| Conversational reasoning | 4/4 grounded; 3.0/3; 1,454 ms | 4/4 grounded; 3.0/3; 1,694 ms | Luna / low | Responses were effectively equivalent; Luna was faster and cost 10× less |
| Lightweight grounded generation | 4/4 grounded; 2.5/3; 1,994 ms | 4/4 grounded; 2.75/3; 2,107 ms | Luna / none | The models split the two non-tie preferences; Terra's one clearer review answer is not enough to justify 9.83× class cost, and it did not fix the concision weakness |

No production route changed. The explicit answer is **no: Terra did not produce enough additional product value to justify using it anywhere in this system.** Keep Luna for all three model-backed task classes. Terra's only clear win was one review-summary phrasing; Luna had one clear comparison-presentation win, six cases tied, grounding and correctness were identical, and Terra cost 10.58× more overall.

## Case-study source summary

- Compared GPT-5.6 Luna and GPT-5.6 Terra on 16 fixed cases: eight structured-understanding, four conversational-reasoning, and four lightweight grounded-generation cases.
- Both models passed 16/16 and all generated outputs passed grounding. Structured quality tied at 8/8; conversation tied at 3.0/3; Terra scored 2.75/3 versus Luna's 2.5/3 on lightweight generation because it phrased one review answer more clearly.
- Side-by-side preference was Luna 1, Terra 1, tie 6. Terra cost $0.054823 versus Luna's $0.00518404 (10.58×), with slower mean generated-response totals in both generated task classes.
- The comparison supports keeping Luna for structured understanding, conversational reasoning, and lightweight generation; production routing was not changed.
