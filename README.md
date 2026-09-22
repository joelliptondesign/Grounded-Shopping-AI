# Designing and Building a Conversational Shopping Agent

**AI product design, engineering, and evaluation.**

Buying a mattress is a considered decision. Customers need help expressing their preferences, understanding differences, and weighing tradeoffs.

Building on customer research from a project I originally worked on at Amazon, I developed a working conversational shopping prototype around one practical question:

**How can AI help customers make confident decisions about high-consideration purchases like mattresses, through natural conversation and recommendations grounded in product information?**

[![Watch Designing Agent Autonomy on YouTube](https://i.ytimg.com/vi/ifKgXvHistc/hqdefault.jpg)](https://www.youtube.com/watch?v=ifKgXvHistc)

[Watch the demo: Designing Agent Autonomy](https://www.youtube.com/watch?v=ifKgXvHistc)

## Designing the experience

I chose the interactions to support different moments in the customer’s decision:

- **Cards and shortlists** make recommendations easy to scan, with reasons to consider each option.
- **Comparison tables** put relevant differences side by side when customers are weighing choices.
- **Conversational answers** keep questions and clarifications lightweight.
- **Animations and task trees** communicate that the agent is working and provide a simple view of the shopping process.
- **Suggested next steps** help customers explore further while keeping conversation open-ended.

The experience lets customers change their minds, revisit products, and move between discovery, comparison, and questions without restarting.

## Engineering the behavior

I connected the interface to a Python backend and live AI responses, implementing the behaviors behind the experience:

- **Intent classification and routing:** identify whether a customer wants recommendations, a comparison, a product answer, or something unrelated, and direct the request appropriately.
- **Conversation state management:** retain preferences across turns, apply corrections, and preserve shopping context through conversational detours.
- **Reference resolution:** connect phrases such as “the second one” to the products actually shown.
- **Recommendation logic:** filter against requirements, score eligible products, and identify useful alternatives and tradeoffs.
- **Model integration and orchestration:** connect language understanding, product selection, and response generation with application rules and product evidence.
- **Grounding and recovery:** check supported claims, handle missing information, and provide a path forward when requests are ambiguous or no product meets the requirements.
- **Progressive delivery:** display validated cards and comparisons when ready while keeping customers informed as the response finishes.

## Evaluating the system

I built evaluations for individual requests and complete shopping journeys, covering changing preferences, comparisons, cold starts, and recovery.

The framework assesses **system integrity**—respecting requirements and product facts—and **shopping experience**—understanding the customer and helping them move forward.

Recorded results include:

- **193 passing unit tests.**
- **25 of 26 passing deterministic behavior cases**, with all checked critical integrity rules passing.
- **5 of 6 passing live conversational-reference cases.**

Saved reports preserve failures and opportunities for improvement. A separate model comparison examines response quality, speed, and cost.

## Focused scope

A controlled catalog of 48 mattresses and corresponding review records supports repeatable demonstrations and evaluation. Demo and Live modes share the same interface, allowing both scripted walkthroughs and real AI conversations.

## What this demonstrates

I translate customer needs into interaction decisions, working AI behavior, and measurable evaluations. This project connects my product design practice with hands-on engineering across conversational systems, recommendations, model integration, and testing.

[Full case study](README-PORTFOLIO.md) · [How it works and local setup](docs/TECHNICAL_OVERVIEW.md) · [Evaluation approach](docs/EVALUATION.md) · [Recorded results](artifacts/evals/INDEX.md)
