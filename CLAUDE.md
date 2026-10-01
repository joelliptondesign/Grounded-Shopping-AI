# Groundwork entry point

Read [AGENTS.md](AGENTS.md) for the shared repository working instructions and [Project Context](docs/PROJECT-STATE.md) for current state. Use [SOURCE-MAP.md](docs/SOURCE-MAP.md) to find task-specific guidance.

Frontend-specific instructions are in [frontend/CLAUDE.md](frontend/CLAUDE.md).

<!-- groundwork:generated:conversation-scrolling:start -->
**Conversation scrolling** · Accepted

- When a typed message or suggested-reply pill is submitted, position the new user message at the top of the chat viewport.
- Use native smooth scrolling for that initial move; use immediate positioning for reduced-motion preferences.
- Keep the viewport steady while the response grows. Respect manual scrolling; the next user submission starts a new position.

**Why:** Keep the question and the beginning of the response visible so the user can read naturally, rather than being pulled to the end.

[Full decision: DR-0001](docs/decisions/DR-0001-scrolling-conflict.md)
<!-- groundwork:generated:conversation-scrolling:end -->

<!-- groundwork:entry:start -->
Read [.groundwork/core/WORKFLOW.md](.groundwork/core/WORKFLOW.md) and the project's current context and owner guides before consequential work. Project-specific instructions outside this block remain authoritative within their scope. Missing metadata blocks the affected check, not all work.
<!-- groundwork:entry:end -->
