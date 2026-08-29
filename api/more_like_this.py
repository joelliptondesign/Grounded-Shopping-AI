"""The backend half of the prototype's per-category "see more" action.

The design source answers "see more" with two further products in the same
category, under a bold heading, using the same cards.  Live mode keeps that
interaction but gets the products from the real agent instead of a fixture
lookup: the shopper's current decision result already holds every eligible,
ranked candidate for their state, so this only chooses among products the engine
has already admitted.

Nothing here filters, re-ranks against preferences, or invents rationale. It
reorders already-eligible candidates by the category the shopper tapped, then
hands them back through ``engine.presentation`` so the cards are built by the
same deterministic code that builds a normal recommendation turn.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from engine.presentation import build_turn_presentation


EXTRA_PRODUCTS = 2

# Category headings the frontend sends back are the ones assign_roles() wrote,
# so they map cleanly onto the dimension that earned them.
CATEGORY_DIMENSION = {
    "cooling": "cooling",
    "motion isolation": "motion_isolation",
    "support": "support",
    "feel": "firmness",
    "firm": "firmness",
}

HEADINGS = {
    "cooling": "More options with strong cooling",
    "motion_isolation": "More options that keep movement contained",
    "support": "More options with strong support",
    "firmness": "More options with a similar feel",
    "value": "More value picks worth a look",
    "premium": "More premium options",
    "overall": "More strong all-around options",
}
DEFAULT_HEADING = "More options like these"


def _category_key(category: str) -> str:
    """Read the tapped category heading back into what it was ranking on."""
    lowered = (category or "").casefold()
    for phrase, dimension in CATEGORY_DIMENSION.items():
        if phrase in lowered:
            return dimension
    if "value" in lowered or "price" in lowered or "budget" in lowered:
        return "value"
    if "premium" in lowered:
        return "premium"
    if "best overall" in lowered or "balanced" in lowered:
        return "overall"
    return "default"


def heading_for(category: str) -> str:
    return HEADINGS.get(_category_key(category), DEFAULT_HEADING)


def _order_for_category(
    candidates: List[Dict[str, Any]], category: str
) -> List[Dict[str, Any]]:
    """Reorder already-eligible candidates to suit the tapped category.

    Ranking order is preserved as the tiebreak, so the agent's own judgement
    still decides between products that are equal on the category dimension.
    """
    key = _category_key(category)
    ranked = list(enumerate(candidates))
    if key in {"cooling", "motion_isolation", "support"}:
        ranked.sort(key=lambda item: (-(item[1].get(key) or 0), item[0]))
    elif key == "value":
        ranked.sort(key=lambda item: (item[1].get("price") or float("inf"), item[0]))
    elif key == "premium":
        ranked.sort(key=lambda item: (-(item[1].get("price") or 0), item[0]))
    return [candidate for _index, candidate in ranked]


def additional_products(
    decision_result: Optional[Dict[str, Any]],
    state: Dict[str, Any],
    category: str,
    already_shown: List[str],
    *,
    limit: int = EXTRA_PRODUCTS,
) -> Tuple[Optional[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """Build the presentation for more products in one category.

    Returns ``(presentation, sku_ids, candidates)``, or empties when the shopper
    has already seen everything the engine considers eligible.
    """
    decision_result = decision_result or {}
    if decision_result.get("decision") != "ALLOW":
        return None, [], []

    seen = set(already_shown or [])
    seen.update(_previously_shown(state))
    remaining = [
        candidate
        for candidate in decision_result.get("ranked_candidates", [])
        if candidate.get("sku_id") and candidate["sku_id"] not in seen
    ]
    if not remaining:
        return None, [], []

    chosen = _order_for_category(remaining, category)[:limit]
    sku_ids = [candidate["sku_id"] for candidate in chosen]

    # Rebuild the cards through the engine's own presentation code so the
    # rationale, tradeoffs and service indicators come from the same place a
    # normal recommendation turn gets them.
    sub_turn = {
        "intent": "recommend",
        "preference_state": state,
        "decision_result": {
            "decision": "ALLOW",
            "ranked_candidates": chosen,
            "metadata": decision_result.get("metadata", {}),
            "match_type": decision_result.get("match_type"),
        },
        "shopping_selection": {
            "selected_product_ids": sku_ids,
            "selection_mode": "exploratory_shortlist",
            "selection_reasons": {},
        },
        "grounding_evidence": {},
        "review_debug": {},
    }
    return build_turn_presentation(sub_turn), sku_ids, chosen


def _previously_shown(state: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for record in state.get("recent_presentations") or []:
        ids.extend(record.get("product_ids") or [])
    return ids


def record_presentation(
    state: Dict[str, Any], shown: List[str], added: List[str], names: List[str]
) -> None:
    """Extend the shopper's reference scope, as a recommendation turn would.

    "See more" adds to what is on screen rather than replacing it, so a later
    "compare the first two" still resolves to the original two — matching the
    design source, where ``moreFor()`` appends to ``ctx.recent``.
    """
    ordered = list(dict.fromkeys(list(shown) + list(added)))
    recent = list(state.get("recent_presentations") or [])
    recent.append(
        {
            "modality": "recommendation_cards",
            "product_ids": ordered,
            "product_names": list(
                dict.fromkeys((state.get("recent_product_names") or []) + names)
            ),
            "action": "recommend_products",
            "product_attribute": None,
            "service_attribute": None,
            "information_source": None,
            "review_topic": None,
        }
    )
    state["recent_presentations"] = recent[-4:]
    state["recent_product_names"] = list(
        dict.fromkeys((state.get("recent_product_names") or []) + names)
    )
    state["pending_elicitation"] = deepcopy(state.get("pending_elicitation"))
