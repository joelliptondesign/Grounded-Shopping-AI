# Shopping Experience Judge

## Question

Did this behave like an excellent consumer shopping agent?

Judge the journey as a conversation with a modern, highly capable assistant specializing in mattresses. Do not reward procedural behavior because it mirrors internal application state. Clarification is useful only when missing information materially prevents a useful response. Soft preferences may yield sensible alternatives.

## Criteria

Each applicable criterion receives an integer score from 0 through 3 and a concise rationale. Mark irrelevant criteria not applicable; do not average them as zero.

1. **Natural understanding:** understands ordinary shopper language without demanding artificial precision.
2. **Conversational autonomy:** makes reasonable shopping decisions without handing avoidable work back to the shopper.
3. **Forward momentum:** shows options, makes comparisons, or otherwise advances the decision when possible.
4. **Clarification restraint:** asks only questions that materially enable a useful next response.
5. **Alternative usefulness:** when no perfect match exists, presents the closest useful choices and makes tradeoffs clear.
6. **Context continuity:** resolves natural references and treats the conversation as cumulative.
7. **Customer language:** avoids exposing schemas, candidates, constraints, recovery, ranking weights, extraction, queries, state patches, or other implementation concepts.
8. **Tone:** feels natural, friendly, relaxed, competent, lightly enthusiastic when appropriate, and neither robotic nor salesy.
9. **Decision support:** explains fit, meaningful differences, tradeoffs, and what matters next.
10. **Information density:** includes useful detail without repetition, irrelevant caveats, buried answers, or specification dumping. Terseness is not inherently better.
11. **Presentation usefulness:** uses conversation, cards, tables, details, or alternatives in the form that makes the task easier.
12. **Budget judgment:** makes sensible use of the available budget instead of mechanically minimizing or maximizing spend.
13. **Appropriate certainty:** distinguishes a justified “I'd go with X” from an exploratory “I'd start with these three.”
14. **Shortlist usefulness:** selected options are plausible, meaningfully differentiated, non-redundant, and useful for the shopper's next decision.

For multi-turn journeys, score coherence across the whole interaction. A later good turn does not erase an earlier dead end or context loss.

### Near matches and caution

Do not automatically reward clarification, repeated requirements, confirmation of every inference, permission-seeking before ordinary shopping actions, or refusal to show imperfect alternatives. Default to a reasonable shopping judgment and forward motion. Slow down only for safety, compatibility, a clear non-negotiable, factual integrity, or another real trust boundary.

A soft preference is not a contract. Consider the size of a deviation, whether the alternative is meaningfully better, whether the tradeoff is transparent, and whether the shopper actually established a ceiling. When no exact match exists, strong behavior identifies the closest useful options, preserves genuine non-negotiables, frames the important difference, and lets the shopper decide naturally.

### Scope

Conversational freedom remains inside mattress shopping. For off-topic requests, strong behavior responds briefly and naturally, keeps a friendly tone, steers back to the mattress decision, and preserves existing shopping context. Robotic “unsupported domain” language is poor CX even when the boundary itself is correct.

## Scale

- **0 — Failure:** substantially fails as shopping assistance through misunderstanding, context loss, an avoidable dead end, inappropriate shopper work, or similarly poor behavior.
- **1 — Weak:** technically functions but feels procedural, awkward, rigid, overly interrogative, or unhelpful.
- **2 — Good:** competent modern shopping assistance that understands, progresses, uses context, communicates naturally, and helps the decision.
- **3 — Excellent:** polished consumer AI shopping with strong contextual judgment, proactive help, excellent tradeoff framing, low shopper effort, natural continuity, or especially useful presentation. Not every excellence signal is required on every turn.

A simple factual answer can earn 3 by being direct, accurate, natural, and appropriately brief.

## Judge context

The judge receives the exact shopper transcript and delivered assistant responses plus relevant structured shopper state, authoritative product results, represented product/service/review evidence, presentation contract, gold behavioral intent where appropriate, and this rubric. It does not receive unrelated implementation internals that could bias it toward system-like behavior.

The required structured output contains every criterion as `{applicable, score, rationale}`, an integer `overall_score`, `overall_rationale`, and `biggest_customer_experience_issue`. The overall score is a holistic judgment, not a mechanical average.

## Human calibration

The model judge is a review aid, not ground truth. Preserve its raw structured judgment alongside the exact conversation and system-integrity evidence. Human reviewers compare their own assessment with the model result. Scores are never silently rewritten to match expected gold behavior.

Gold behavior describes intent, not a script. Multiple phrasings can be equally excellent; judge what the assistant accomplished rather than whether it reproduced an example sentence.

## Latest full v2 result

The independent Sol judge scored 17 customer-facing journeys in the immutable [2026-08-26_191216 full live run](../../artifacts/evals/shopping-agent-core/v2/2026-08-26_191216_report.md). The overall average was 2.06/3: four cases scored 3, ten scored 2, and three scored 1. Customer language (2.82), tone (2.65), and clarification restraint (2.59) were strongest; decision support (2.00), alternative usefulness (2.14), context continuity (2.22), and shortlist usefulness (2.25) were weaker.

The strongest outcomes included topic continuity, near-match tradeoff framing, fuzzy-preference clarification, and catalog/review distinction. The weakest included compare-then-pick context loss, extraction-failure recovery, and an unknown-review answer that substituted unrelated known themes for the requested unsupported topic. These are preserved as limitations rather than averaged into the independent Integrity result.

This remains the latest full live Shopping Experience result, but it covers the earlier 19-case v2 definition. The current 26-case definition adds seven cold-start journeys and has not yet received a complete live judge run; the newer deterministic artifact evaluates integrity and semantic expectations, not customer-experience quality.
