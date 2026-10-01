# Rufus Shopping Agent Prototype — project rules

## Scrolling

Approved by J.L., October 1, 2026. [Agent Decision Record](../docs/decisions/DR-0001-scrolling-conflict.md).

On a typed message or suggested-reply pill, use native smooth scrolling to place the new right-aligned user message at the top of the chat viewport. Keep that position while the assistant response appears below it. Do not follow the response to its bottom or reposition to an assistant introduction/card. Users can scroll manually without being pulled back by subsequent content. The next user submission starts a new position. Provide enough space for short turns to reach the top; respect reduced motion.
