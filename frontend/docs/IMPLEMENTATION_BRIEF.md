# Rufus Prototype — Claude Design Implementation Brief

## Objective

Build a polished, mobile-first, fixture-backed Rufus shopping experience that can be used directly in a UX / AI Product Design portfolio.

The prototype must look credible in static screenshots and short screen recordings.

Prioritize visual fidelity and interaction polish over backend sophistication.

## Important

Do not integrate with the existing shopping-agent repository yet.

Build the UI against fixture data and simple deterministic state transitions.

However, keep presentation components cleanly separated from fixture data so real backend responses can replace the fixtures later.

## Primary target

Design for an iPhone-sized viewport first.

Recommended working viewport:
- 390px wide
- approximately 844px tall

The page should remain usable responsively, but desktop polish is not the current priority.

## Required states

Implement these states as one continuous interaction:

1. Cold start
2. Customer sends initial mattress request
3. Multi-step progress state
4. Recommendation result
5. Customer asks to compare
6. Comparison result
7. Customer asks about setup / haul-away
8. Service verification progress
9. Grounded service answer
10. Customer changes budget
11. Updated recommendation / recovery result

## Interaction requirements

### Realistic latency

Do not make fixture responses instantaneous.

Use scripted delays so the demo feels like a real consumer AI experience.

Suggested ranges:
- Simple conversational transition: 500–1200 ms
- Recommendation request: 3–5 s
- Comparison: 1.5–3 s
- Service verification: 2–4 s
- Updated recommendation: 2–4 s

These do not need to be exact. They should simply feel believable.

### Progress states

Progress steps should appear incrementally.

Example:
- Understanding what matters to you
- Checking matching mattresses
- Comparing cooling and comfort
- Preparing recommendations

The active step uses a blue indicator.

Earlier steps should appear complete or subdued.

Once the response is ready, collapse or remove the progress trace cleanly.

### Scrolling

New content should scroll into view naturally.

Avoid abrupt page jumps.

Do not automatically force the viewport to the absolute bottom if that makes the user lose context.

### Composer

The composer remains available throughout the conversation.

Use fixture-aware interactions so the scripted demo can be completed by:
- typing the expected message, and/or
- selecting optional suggested replies

The primary visual should still feel like free-form conversation.

## Component structure

Prefer reusable presentation components such as:

- `RufusHeader`
- `ChatComposer`
- `UserMessage`
- `RufusText`
- `ProgressTrace`
- `DotLoader`
- `ProductCard`
- `RecommendationSection`
- `ComparisonView`
- `ServiceSummary`
- `SuggestedReplies`

Keep fixture content outside these components.

## Suggested presentation contract

Fixture responses can use a simple shape conceptually similar to:

```ts
type TurnPresentation =
  | { type: "conversation"; text: string }
  | { type: "recommendations"; text: string; products: Product[] }
  | { type: "comparison"; text: string; rows: ComparisonRow[] }
  | { type: "service"; text: string; services: ServiceStatus[] }
  | { type: "recovery"; text: string; products: Product[] };
```

This is only a suggested separation of concerns.

Do not over-engineer schemas or state management.

## Visual fidelity

Use `VISUAL_REFERENCE.md` as the visual source of truth.

The experience should feel like Amazon Rufus, not a generic chatbot or SaaS AI assistant.

Avoid:
- gradients
- glassmorphism
- oversized AI icons
- purple AI branding
- chat avatars
- “agent thinking” panels
- developer terminology
- decorative dashboards
- excessive cards

## Portfolio priorities

The prototype needs to clearly demonstrate:

- Natural conversational input
- Useful agent autonomy
- Adaptive UI
- Grounded service information
- Recovery when preferences change

Evaluation, model selection, latency benchmarking, and system architecture do not need dedicated UI.

## Build quality

This is a portfolio prototype, but interactions should feel intentional:
- no broken controls
- no placeholder copy
- no layout jumps
- no fake debug output
- no obviously unfinished states
- no dead-end buttons in the hero flow

The hero fixture journey should work reliably every time.
