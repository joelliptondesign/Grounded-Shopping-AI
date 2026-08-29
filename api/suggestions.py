"""Contextual continuation pills, in the Claude Design prototype's voice.

The prototype never ends a turn in a dead end: a recommendation is followed by
"Compare the first two", "Which sleeps coolest?", "How do I get rid of my old
mattress?", and a comparison by its own set.  Those fixtures are the wording
reference; what is offered here is chosen from the live shopper state and the
products actually on screen, so the pills change as the conversation moves.

Every pill is a plain shopper utterance.  Clicking one posts it as an ordinary
message, so it runs through the same engine turn as anything typed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


MAX_REPLIES = 3

PRIORITY_QUESTIONS = {
    "cooling": "Which sleeps coolest?",
    "motion_isolation": "Which is best if my partner moves a lot?",
    "support": "Which gives the most support?",
    "firmness": "Which feels firmest?",
    "price": "Which is the best value?",
}
DEFAULT_QUESTION = "Which would you pick for me?"
REVIEWS = "What do customers say?"
HAUL_AWAY = "How do I get rid of my old mattress?"
DELIVERY = "What are the delivery options?"
CHEAPER = "Show me something cheaper"


def _top_priority(state: Dict[str, Any]) -> Optional[str]:
    """The dimension the shopper cares about most, as the engine recorded it."""
    order = {"critical": 3, "high": 2, "medium": 1}
    ranked = sorted(
        (
            (order.get(level, 0), field)
            for field, level in (state.get("priorities") or {}).items()
            if level and order.get(level, 0) > 0
        ),
        key=lambda item: (-item[0], item[1]),
    )
    return ranked[0][1] if ranked else None


def _budget(state: Dict[str, Any]) -> Optional[float]:
    soft = state.get("soft_preferences") or {}
    hard = state.get("hard_constraints") or {}
    for value in (soft.get("budget_target"), hard.get("max_price")):
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _cheaper_reply(state: Dict[str, Any], products: List[Dict[str, Any]]) -> str:
    """Name a concrete lower target when one is grounded, as the prototype does."""
    budget = _budget(state)
    prices = [
        item["price"] for item in products if isinstance(item.get("price"), (int, float))
    ]
    anchor = budget if budget is not None else (min(prices) if prices else None)
    if anchor is None:
        return CHEAPER
    target = int(round(anchor * 0.8 / 50.0)) * 50
    if target < 100:
        return CHEAPER
    return f"Show me something closer to ${target:,}"


def _asked_about(state: Dict[str, Any], key: str) -> bool:
    """Whether a recent presentation already covered reviews or services."""
    for record in state.get("recent_presentations") or []:
        if key == "reviews" and record.get("information_source") == "reviews":
            return True
        if key == "service" and record.get("action") == "answer_service_question":
            return True
    return False


HAUL_SCHEDULING = "Can haul-away happen on delivery day?"
BACK_TO_PICKS = "Back to my earlier picks"


def _candidates(
    modality: str,
    state: Dict[str, Any],
    products: List[Dict[str, Any]],
    service_discovery: bool = False,
    service_answered: bool = False,
) -> List[str]:
    priority = _top_priority(state)
    question = PRIORITY_QUESTIONS.get(priority, DEFAULT_QUESTION)
    count = len(products)

    if service_discovery:
        # The prototype follows haul-away alternatives with comparison, the
        # scheduling question, and a way back to what they were looking at.
        return [
            "Compare these two" if count == 2 else question,
            HAUL_SCHEDULING,
            BACK_TO_PICKS,
            REVIEWS,
        ]

    if modality == "recommendation_cards":
        pills = []
        if count >= 2:
            pills.append("Compare the first two" if count > 2 else "Compare these two")
        pills.append(question)
        if not _asked_about(state, "reviews"):
            pills.append(REVIEWS)
        pills.append(_cheaper_reply(state, products))
        if not service_answered and not _asked_about(state, "service"):
            pills.append(HAUL_AWAY)
        pills.append(DEFAULT_QUESTION)
        return pills

    if modality == "comparison_table":
        return [
            question,
            REVIEWS,
            "Does either include haul-away?",
            DEFAULT_QUESTION,
            _cheaper_reply(state, products),
        ]

    if modality == "product_detail":
        name = (products[0].get("name") if products else None) or "this one"
        return [
            REVIEWS,
            f"How does {name} compare to the others?",
            DELIVERY,
            _cheaper_reply(state, products),
        ]

    # Conversational answers — a product, review or service question. The
    # prototype always leaves a way forward from these.
    pills = []
    recent = state.get("recent_product_names") or []
    if len(recent) >= 2:
        pills.append("Compare the first two")
    if not _asked_about(state, "reviews"):
        pills.append(REVIEWS)
    pills.append(question)
    if not service_answered and not _asked_about(state, "service"):
        pills.append(HAUL_AWAY)
    pills.append(_cheaper_reply(state, products))
    pills.append("Show me other options")
    return pills


def suggested_replies(
    modality: str,
    state: Dict[str, Any],
    products: List[Dict[str, Any]],
    *,
    previous: Optional[List[str]] = None,
    has_context: bool = True,
    service_discovery: bool = False,
    service_answered: bool = False,
    asked: Optional[str] = None,
) -> List[str]:
    """Up to three pills for this turn, avoiding a verbatim repeat of the last set."""
    if not has_context:
        return []
    previous_set = set(previous or [])
    # Never offer back the question the shopper just asked.
    just_asked = (asked or "").strip().casefold().rstrip("?.!")
    ordered = [
        pill
        for pill in dict.fromkeys(
            _candidates(modality, state, products, service_discovery, service_answered)
        )
        if pill.strip().casefold().rstrip("?.!") != just_asked
    ]
    fresh = [pill for pill in ordered if pill not in previous_set]
    # Keep offering the genuinely useful ones rather than running dry.
    return (fresh + [pill for pill in ordered if pill in previous_set])[:MAX_REPLIES]
