# Designing and Building a Conversational Shopping Agent

**AI product design, working implementation, and evaluation**

[![Watch Designing Agent Autonomy on YouTube](https://i.ytimg.com/vi/ifKgXvHistc/hqdefault.jpg)](https://www.youtube.com/watch?v=ifKgXvHistc)

[Watch the video: Designing Agent Autonomy — Joel Lipton](https://www.youtube.com/watch?v=ifKgXvHistc)

I built a conversational shopping prototype that helps people discover, compare, and refine mattress choices through natural conversation. A shopper can describe what matters, change their mind, ask about reviews or services, and return to earlier options without starting over.

My focus was the relationship between the experience and the system behind it: deciding how an assistant should behave, translating those decisions into working software, and evaluating whether the behavior holds across a conversation.

The project brings together a shopper interface, a Python recommendation engine, live language-model integration, session memory, response validation, and repeatable evaluations. It demonstrates how I approach AI product design with the implementation depth needed to build and investigate the experience myself.

## The product challenge

Shopping decisions rarely arrive as complete specifications. Someone might begin with “I sleep hot,” offer a budget later, compare two options, and then ask whether the second one includes haul-away. They may also change their priorities or briefly leave the topic altogether.

I wanted the experience to accommodate that behavior while keeping its recommendations tied to represented product information. The assistant needs to understand ordinary language, remember relevant details, recognize uncertainty, and help the shopper move forward.

That led to several concrete design questions:

- When is there enough information to show useful options?
- When does a comparison need a table rather than another paragraph?
- How should the assistant distinguish a preference from a non-negotiable requirement?
- How can waiting feel understandable without overstating what the system is doing?
- What should happen when no product fits, a reference is ambiguous, or the model makes a mistake?

## Designing the interactions

The response format is part of the product's decision-making. Different shopping tasks need different ways of presenting information.

| Interaction choice | Customer purpose | How it works in the prototype |
| --- | --- | --- |
| Product cards and shortlists | Make exploration easy to scan | Show selected products with prices, match reasons, and tradeoffs; support further exploration through “see more.” |
| Comparison tables | Make differences directly comparable | Align represented attributes for the selected products, with the shopper's priorities informing the presentation. |
| Conversational answers | Keep simple exchanges lightweight | Answer narrow questions or ask for clarification without forcing a new set of product cards. |
| Suggested replies and choice lists | Reduce effort at useful decision points | Offer relevant next questions, clarification options, or recovery choices while keeping free-form input available. |
| Loading animation and progress cues | Acknowledge the request and explain the wait | Use a lightweight dots treatment for simple exchanges and a progress timeline for more involved shopping work. |
| Task trees | Give shoppers a simple account of the work underway | Summarize shopping activity in customer-facing language, offering lightweight process visibility rather than an internal reasoning trace. |

The task tree is deliberately restrained: one per turn, with simple loading feedback for later pauses. In Live mode, content arrives according to backend readiness. Validated product cards or a comparison can appear before the accompanying prose is finished, and a loading cue remains visible until the turn completes.

This creates a practical connection between interaction design and engineering. The interface needs to know what is ready, what is still pending, and when the shopper can consider a response complete. The backend exposes those boundaries, and the frontend presents them coherently.

Implementation details: [shopper interface](frontend/README.md), [presentation logic](engine/presentation.py), and [progressive response delivery](api/turn_stream.py).

## Making conversation work across turns

The assistant keeps a structured record of the shopper's needs alongside recent conversation. If someone changes their budget, the application updates that detail while retaining their size and cooling preference unless they also change those.

It also records what the shopper actually saw, including the identity and order of displayed products. This gives phrases such as “the second one” and “compare the first two” a concrete reference. The application checks the model's interpretation against those records and can retry or clarify when it cannot resolve the request reliably.

The distinction between preferences and requirements is equally important. “Around $1,000” can support nearby alternatives with an explained tradeoff. “I absolutely cannot spend more than $1,000” establishes a ceiling. When genuine requirements leave no eligible products, the assistant can offer verified ways forward and wait for acceptance before changing a requirement.

These behaviors support a conversation in which people can explore, correct themselves, and ask follow-up questions without having to restate their entire request.

Implementation details: [conversation handling](engine/conversation.py), [preference updates](engine/preference_extraction.py), and [recovery logic](engine/recovery.py).

## Building the recommendation system

The project includes a recommendation engine with explicit, inspectable rules. It checks product eligibility against the shopper's requirements, scores eligible products using represented attributes and preferences, and identifies tradeoffs and near matches.

A language-model step then chooses useful options from the eligible set. This allows the assistant to offer either a confident primary recommendation or an exploratory shortlist, depending on the available information. Application code checks the selection, its product identities, and its supporting reasons before accepting it.

The division of responsibility is deliberate:

| Responsibility | Implementation |
| --- | --- |
| Understand informal language and conversational references | Language model with a structured response format |
| Remember requirements and preferences | Application-managed session state |
| Determine eligibility and calculate ranking signals | Python recommendation engine |
| Choose useful options within the eligible set | Bounded model selection with validation |
| Supply product and review evidence | Separate local catalog and review fixtures |
| Select cards, tables, details, or conversation | Application presentation logic |
| Write customer-facing explanations | Language model, followed by grounding checks |

Generated prose is buffered for validation before it reaches the shopper. Failed validation can trigger a stricter retry and then a fallback assembled from represented facts. These checks address specific supported claims and failure modes; their effectiveness is something the evaluations test.

Implementation details: [recommendation engine](engine/decision.py), [shopping selection](engine/shopping_selection.py), [grounding checks](engine/grounding.py), and [architecture guide](docs/ARCHITECTURE.md).

## Evaluating both reliability and experience

I built an evaluation framework around the behaviors the product is supposed to deliver. It includes individual requests, conversations spanning multiple turns, cold starts, product references, recovery, and adversarial examples of unsupported claims.

The framework separates two questions:

**System integrity:** Does the assistant respect requirements, preserve valid shopping state, and stay within represented evidence?

**Shopping experience:** Does it understand the shopper, ask useful questions, explain tradeoffs, and maintain momentum?

Keeping those assessments separate makes the results more useful. A factually safe response can still be frustrating or miss the shopper's question. A fluent response can still violate an important requirement.

Deterministic evaluations exercise application behavior with fixed inputs. Live evaluations exercise model behavior and preserve the resulting conversations. Saved reports retain failures, configuration, and supporting outputs so changes can be investigated. The project also includes a controlled model comparison to examine quality, latency, and cost.

### Recorded evidence

These are historical results from small, defined evaluation sets, not production performance claims or customer-research findings.

| Evaluation | Recorded result | What it tells me |
| --- | --- | --- |
| [Core v2, August 29, 2026](artifacts/evals/shopping-agent-core/v2/2026-08-29_224939_report.md) | 25 of 26 deterministic cases passed; all checked critical invariants passed | The application rules passed the defined integrity checks, with an outstanding expected-winner mismatch. |
| [Reference continuity, August 29, 2026](artifacts/evals/conversational-reference-continuity/v1/2026-08-29_224526_report.md) | 5 of 6 live reference cases passed; system integrity passed | Context and reference handling work across several tested journeys, with a remaining gap. |
| [Experience calibration, August 29, 2026](artifacts/evals/shopping-experience-calibration/v1/2026-08-29_224321_report.md) | Integrity passed in all five journeys; model-judged experience averaged 2.40/3 | Safe behavior and strong experience are separate achievements; the report identifies a missed service-topic follow-up. Human calibration remains pending. |
| [Earlier full live Core v2 run, August 26, 2026](artifacts/evals/shopping-agent-core/v2/2026-08-26_191216_report.md) | 12 of 19 semantic regression cases passed | Broader live testing exposed weaknesses that narrower successful slices cannot establish as resolved. This run predates the seven cold-start cases. |

The remaining failures are useful product evidence: they identify where interpretation, continuity, or presentation still needs work. The [evaluation framework](docs/EVALUATION.md) and [run index](artifacts/evals/INDEX.md) provide the fuller record.

## Purposeful scope

I bounded the project around conversational shopping behavior and its supporting system. That scope makes the experience executable and the decisions testable without requiring a retailer's production infrastructure.

- **A synthetic catalog and review dataset:** 48 products provide controlled conditions for testing tradeoffs, missing information, and conflicting needs. They do not establish recommendation quality for real inventory or real customer reviews.
- **A focused recommendation engine:** Explicit filtering and scoring make decisions inspectable. The project does not attempt large-scale personalization, learned ranking, or a retail recommendation platform.
- **Local commerce data:** There is no production Amazon integration, live inventory, checkout, or fulfillment connection. The Rufus-style interface is a prototype surface. Decorative ratings, delivery labels, and other commerce details are frontend fixtures and do not drive recommendations.
- **Session-level memory:** The assistant remembers the current conversation in memory. Persistent customer profiles, account systems, and production operations remain outside this implementation.
- **Separate Demo and Live modes:** Demo supports repeatable walkthroughs; Live exercises the shopping engine and model integration through the same interface. Evaluation claims refer to their stated test mode.

The shopper interface was imported from a Claude Design prototype and connected to the Python engine through a FastAPI adapter. That provenance is documented in the [frontend README](frontend/README.md). The work represented here includes the interaction decisions, live integration, recommendation and conversation behavior, and evaluation system around that experience.

## What this demonstrates about my practice

I approach AI product design by connecting a customer-facing decision to an implementable behavior and a way to evaluate it. “Remember what matters,” “show a useful comparison,” and “explain why this fits” each require choices across the interface, model instructions, application logic, and testing.

This project demonstrates engineering capabilities relevant to AI engineering and forward-deployed work: translating ambiguous needs into concrete behavior, integrating a model with an existing interface, building rules around domain data, investigating failures, and weighing experience quality against response time and cost. Its evidence is a working prototype and recorded evaluations; customer deployment and production operations would be a separate body of work.

**The result is an AI shopping experience I can demonstrate, inspect, and improve—from the interaction a shopper sees to the system behavior that produces it.**

## Explore the project

- [Run the application and see how it works](docs/TECHNICAL_OVERVIEW.md)
- [Read the product-level architecture](docs/ARCHITECTURE.md)
- [Explore the interface and Live mode](frontend/README.md)
- [Review the evaluation approach](docs/EVALUATION.md)
- [Inspect recorded evaluation runs](artifacts/evals/INDEX.md)
- [Read the model-selection experiment](docs/MODEL_BAKEOFF.md)
