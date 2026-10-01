# DR-0001 Keep the submitted user message at the top

Type: Agent Decision Record
Date: October 1, 2026 (original conflict recorded September 30)
Decider: J.L. (Joel Lipton)
Scope: frontend conversation scrolling in Demo and Live

<!-- groundwork:decision-summary:start -->
```json
{
  "version": 1,
  "id": "DR-0001",
  "title": "Conversation scrolling",
  "status": "accepted",
  "summary": [
    "When a typed message or suggested-reply pill is submitted, position the new user message at the top of the chat viewport.",
    "Use native smooth scrolling for that initial move; use immediate positioning for reduced-motion preferences.",
    "Keep the viewport steady while the response grows. Respect manual scrolling; the next user submission starts a new position."
  ],
  "rationale": "Keep the question and the beginning of the response visible so the user can read naturally, rather than being pulled to the end."
}
```
<!-- groundwork:decision-summary:end -->

## Context

The earlier frontend/CLAUDE.md rule required native smooth follow-to-bottom with no custom anchoring. The implementation instead pinned assistant introductions/product results and used timed custom easing. The September 30 audit recorded this as unresolved and preserved behavior pending clarification. Neither fully described the intended interaction.

## Options and recommendation

1. Follow each new assistant block to the bottom. Keeps the newest content visible but can leave the reader looking at the end before reading the beginning.
2. Keep the existing assistant-introduction/result pin and custom easing. Shows results from their beginning but can move away from the user's question and reposition the reader as more blocks arrive.
3. Move the newly submitted user message to the top once, then keep the viewport steady while the response appears beneath it. Preserves question/answer context and natural reading order. Short turns need reserved space to make the top position reachable.

J.L. selected option 3. Codex's implementation recommendation is native smooth scrolling for the initial move and dynamic reserved space below the active turn; no custom timed animation or repeated response-following.

## Decision and rationale

When a user submits a typed message or presses a suggested-reply pill, place the new right-aligned user message at the top of the chat viewport. Hold that position while the agent generates below it. J.L.'s rationale: seeing the beginning allows natural reading, whereas jumping to the end of the agent's response is confusing. The behavior matters more than a particular animation; native smooth scrolling is sufficient.

Manual scrolling remains under the reader's control. Later response blocks must not pull them back. The next user submission starts a new position. Respect reduced-motion preferences by using immediate positioning.

Decision source: direct October 1 clarification in this conversation, followed by explicit approval: “this qualifies as a as Agent Decision Record - approved by me. J.L.” J.L. then requested updating this existing record with the decision, rationale and implementation in the repository ADR format. This supersedes the former follow-to-bottom instruction; it is the shared product contract, not a temporary task exception.

## Evidence and consequences

Implementation owner: Codex, under J.L.'s approved behavior.

- [Frontend implementation](../../frontend/Rufus%20Shopping%20Agent.dc.html): submit schedules one movement to the latest user message; reveal maintains reserved space and uses native scrollTo once. ResizeObserver adjusts that space as content/viewport height changes without issuing new scroll commands.
- A short turn reserves sufficient trailing space for its user message to reach the top. Growing content consumes that space, avoiding permanent empty space after long responses.
- Wheel, touch and pointer input explicitly cancel an in-flight native animation so the reader can take over.
- Custom glide easing and assistant-result pinning are removed. Reset clears pending movement and reserved space. Unmount disconnects the observer. Reduced motion skips smooth animation.
- Product-card “see more” retains the current reading position because it does not submit a new user message.
- [Frontend rules](../../frontend/CLAUDE.md) and [frontend guide](../../frontend/README.md#conversation-scrolling) carry the current contract.
- [Verification record](../work/SCROLLING-2026-10-01.md) distinguishes browser observations, automated checks and untested areas.

## Acceptance and follow-up

Accepted by J.L. on October 1, 2026. Approval covers the interaction contract and use of native smooth scrolling. Implementation details above are Codex's execution choices, not a claim that J.L. reviewed the resulting code or all runtime paths.

Verify typed submission, suggestion pills, response growth, short replies, manual scrolling and reset. Demo and Live share presentation code; Live backend integration, all browser/device combinations and virtual-keyboard behavior require separate coverage. Preserve this record's identity and original conflict as history. A future change to the intended behavior requires a new explicit decision or a documented amendment.
