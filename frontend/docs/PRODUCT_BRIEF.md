# Rufus Shopping Agent Prototype — Product Brief

## Goal

Create a polished, mobile-first Amazon Rufus shopping experience for a UX / AI Product Design portfolio case study.

The experience should look and feel like a real Amazon consumer product in screenshots and short videos.

This is a fixture-backed prototype for now. Do not integrate with the existing shopping-agent repository yet.

## Business problem

Mattress returns are expensive. Once used, many mattresses cannot simply be resold, which creates significant operational cost across returns, disposal, and logistics.

Buying a mattress online is also unusually difficult because customers cannot touch or try the product before purchasing, yet comfort is highly personal.

The product goal is simple:

**Help customers choose the right mattress before purchase so they are more confident in the decision and less likely to return it.**

The broader framework applies to other high-consideration products such as furniture, appliances, and consumer electronics. “High consideration” means expensive or consequential purchases where customers need to weigh multiple factors before deciding.

## Key AI Product Design beats

The prototype should demonstrate these behaviors without exposing technical implementation details.

### 1. Agent autonomy

The agent should understand subjective needs, remember preferences across the conversation, weigh trade-offs, and make recommendations.

Important customer needs should remain consistently respected.

### 2. Adaptive UI

Conversation is the control layer, not the only output.

The interface can adapt between:
- Conversation
- Recommendation cards
- Comparison views
- Product details
- Recovery choices

### 3. Grounded service information

A real failure observed in earlier AI shopping experiences was confident hallucination about Amazon services such as setup and haul-away.

When the customer asks about delivery, setup, or haul-away, the experience should visibly check verified service information and respond only with what is known.

If something cannot be verified, Rufus should say so rather than guess.

### 4. Recovery

The experience should handle changed preferences, competing needs, imperfect matches, and ambiguous requests without restarting the shopping journey.

## Scope

In scope:
- Mobile-first Rufus experience
- Fixture-backed conversations
- Realistic latency
- Loading/progress states
- Product recommendation cards
- Comparison UI
- Grounded service lookup
- Preference update / recovery
- Basic responsive behavior for desktop later

Out of scope:
- Live Amazon APIs
- Real checkout
- Authentication
- Eval dashboards
- Model routing controls
- Developer/debug traces
- Architecture views
- Production backend integration

## Naming

Use **Rufus** as the assistant name.

Do not use Alexa branding in the prototype.
