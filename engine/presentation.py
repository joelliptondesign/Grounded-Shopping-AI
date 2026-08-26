"""Deterministic presentation contracts for conversational shopping turns.

This module chooses structure from intent and authoritative result shape.  It
does not filter, rank, or ask a language model to decide how results render.
"""

from copy import deepcopy
from typing import Any, Dict, List, Optional

from engine.grounding import AUTHORITATIVE_SOURCES


MODALITIES = (
    "conversation",
    "recommendation_cards",
    "comparison_table",
    "product_detail",
    "recovery_choices",
)

PRODUCT_FACT_SOURCE = AUTHORITATIVE_SOURCES["product_facts"]
SERVICE_SOURCE = AUTHORITATIVE_SOURCES["service_eligibility"]
RANKING_SOURCE = AUTHORITATIVE_SOURCES["recommendation"]
SCORING_SOURCE = AUTHORITATIVE_SOURCES["candidate_ranking"]
REVIEW_SOURCE = AUTHORITATIVE_SOURCES.get(
    "review_evidence", "precomputed_customer_review_evidence_fixture_v1"
)

DIMENSION_LABELS = {
    "price": "Price",
    "firmness": "Firmness",
    "support": "Support",
    "cooling": "Cooling",
    "motion_isolation": "Motion isolation",
}
PRIORITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, None: 0}


def _contract(modality: str, message: str, reason: str) -> Dict[str, Any]:
    if modality not in MODALITIES:
        raise ValueError(f"Unsupported presentation modality: {modality}")
    return {
        "modality": modality,
        "message": message,
        "products": [],
        "comparison": None,
        "actions": [],
        "suggested_replies": [],
        "elicitation": None,
        "selection_reason": reason,
        "grounding_sources": {},
    }


def _format_value(field: str, value: Any) -> str:
    if value is None:
        return "Unknown"
    if field == "price":
        return f"${value:,.0f}"
    if field in {"firmness", "support", "cooling", "motion_isolation"}:
        return f"{value}/10"
    if field == "contains_latex":
        return "Contains latex" if value else "No latex listed"
    if field == "haul_away_CA_available":
        return "Available" if value else "Not available"
    if field == "available_sizes":
        labels = {"twin_xl": "Twin XL", "cal_king": "Cal King"}
        return ", ".join(labels.get(str(item), str(item).title()) for item in value)
    if field == "trial_days":
        return f"{value} days"
    if field == "warranty_years":
        return f"{value} years"
    return str(value)


def _active_dimensions(state: Dict[str, Any]) -> List[str]:
    priorities = state.get("priorities", {})
    return sorted(
        DIMENSION_LABELS,
        key=lambda field: (-PRIORITY_ORDER.get(priorities.get(field), 0), list(DIMENSION_LABELS).index(field)),
    )


def _relevant_dimensions(state: Dict[str, Any]) -> List[str]:
    priorities = state.get("priorities", {})
    soft = state.get("soft_preferences", {})
    target_keys = {
        "price": "budget_target",
        "firmness": "firmness_target",
        "support": "support_target",
        "cooling": "cooling_target",
        "motion_isolation": "motion_isolation_target",
    }
    ordered = _active_dimensions(state)
    return [
        field
        for field in ordered
        if priorities.get(field) is not None or soft.get(target_keys[field]) is not None
    ]


SELECTION_REASON_LABELS = {
    "strong_overall_fit": "Strong overall fit",
    "strong_all_around_option": "Strong all-around option",
    "good_use_of_budget": "Makes good use of your budget",
    "good_value": "Good value",
    "balanced_fit": "Balanced fit",
    "lower_price_option": "Lower-price option",
    "premium_option": "Premium option",
    "high_cooling": "High cooling: {cooling}/10",
    "strong_motion_isolation": "Strong motion isolation: {motion_isolation}/10",
    "strong_support": "Strong support: {support}/10",
    "closest_firmness_fit": "Closest firmness fit",
    "useful_tradeoff_option": "Useful tradeoff option",
}


def _recommendation_message(
    products: List[Dict[str, Any]],
    state: Dict[str, Any],
    *,
    mode: str,
    near_match: bool = False,
) -> str:
    if not products:
        return "I couldn't find a mattress that matches all of your current requirements."
    winner = products[0]["name"]
    hard = state.get("hard_constraints", {})
    soft = state.get("soft_preferences", {})
    if mode == "exploratory_shortlist":
        if near_match:
            if hard.get("require_CA_haul_away") is True or soft.get("prefer_CA_haul_away") is True:
                with_service = next((item for item in products if item.get("haul_away_CA_available") is True), None)
                lower_price = min(
                    (item for item in products if isinstance(item.get("price"), (int, float))),
                    key=lambda item: item["price"],
                    default=None,
                )
                if with_service and lower_price and with_service != lower_price:
                    return (
                        f"If California haul-away is a must, {with_service['name']} is the one to look at. "
                        f"If price matters more, {lower_price['name']} is the lower-price option."
                    )
            return "Nothing lines up perfectly, but these are the closest useful options for different reasons."
        return "You've got room to choose based on what matters most. I'd start with these options for different reasons."
    if near_match:
        return f"Nothing lines up perfectly, but these are the closest useful options. I'd start with {winner}."
    if len(products) == 1:
        product = products[0]
        if hard.get("exclude_latex") is True and product.get("contains_latex") is False:
            details = []
            requested_size = hard.get("size")
            if requested_size and requested_size in product.get("available_sizes", []):
                details.append(f"available in {requested_size.replace('_', ' ')}")
            if isinstance(product.get("price"), (int, float)):
                details.append(f"priced at ${product['price']:,.0f}")
            details.append("verified latex-free")
            return f"{winner} is the one I'd start with. It's {', '.join(details)}."
        return f"I'd start with {winner}. It's the strongest fit for what you've described."
    return f"I'd start with these options. {winner} is the strongest overall fit for what you've described."


def _card_reasons(product: Dict[str, Any], state: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []
    hard = state.get("hard_constraints", {})
    if hard.get("exclude_latex") is True and product.get("contains_latex") is False:
        reasons.append("Verified latex-free")
    if hard.get("size") and hard["size"] in product.get("available_sizes", []):
        reasons.append(f"Available in {hard['size'].replace('_', ' ')}")
    if hard.get("max_price") is not None and product.get("price") is not None:
        reasons.append(f"Within your ${hard['max_price']:,.0f} maximum")
    for field in _relevant_dimensions(state):
        if field == "price" or field not in product:
            continue
        reasons.append(f"{DIMENSION_LABELS[field]}: {_format_value(field, product[field])}")
        if len(reasons) == 3:
            break
    if not reasons:
        for field in ("support", "cooling", "motion_isolation"):
            if field in product:
                reasons.append(f"{DIMENSION_LABELS[field]}: {_format_value(field, product[field])}")
            if len(reasons) == 2:
                break
    return reasons[:3]


def _selection_reason_labels(product: Dict[str, Any], tags: List[str]) -> List[str]:
    labels = []
    for tag in tags:
        template = SELECTION_REASON_LABELS.get(tag)
        if template:
            labels.append(template.format(**product))
    return labels


def _card_tradeoff(
    product: Dict[str, Any], displayed: List[Dict[str, Any]], state: Dict[str, Any]
) -> Optional[str]:
    relevant = [field for field in _relevant_dimensions(state) if field != "price"]
    for field in relevant:
        values = [item.get(field) for item in displayed if isinstance(item.get(field), (int, float))]
        if values and product.get(field) is not None and product[field] < max(values):
            difference = max(values) - product[field]
            qualifier = "Slightly lower" if difference <= 1 else "Lower"
            return f"{qualifier} {DIMENSION_LABELS[field].lower()}"
    prices = [item.get("price") for item in displayed if isinstance(item.get("price"), (int, float))]
    if prices and product.get("price") is not None and product["price"] > min(prices):
        return "Higher-priced option"
    return None


def _recommendation_cards(turn: Dict[str, Any]) -> Dict[str, Any]:
    decision = turn.get("decision_result") or {}
    selection = turn.get("shopping_selection") or {}
    selected_ids = selection.get("selected_product_ids") or [
        item.get("sku_id") for item in decision.get("ranked_candidates", [])[:3]
    ]
    candidates = {item.get("sku_id"): item for item in decision.get("ranked_candidates", [])}
    ranked = [candidates[sku_id] for sku_id in selected_ids if sku_id in candidates]
    mode = selection.get("selection_mode", "strong_recommendation")
    near_match = decision.get("match_type") == "near_match"
    contract = _contract(
        "recommendation_cards",
        _recommendation_message(
            ranked,
            turn.get("preference_state", {}),
            mode=mode,
            near_match=near_match,
        ),
        "validated near-match shopping selection" if near_match else "validated shopping-agent selection",
    )
    hard = turn.get("preference_state", {}).get("hard_constraints", {})
    soft = turn.get("preference_state", {}).get("soft_preferences", {})
    service_relevant = hard.get("require_CA_haul_away") is True or soft.get("prefer_CA_haul_away") is True
    tradeoffs_by_sku = decision.get("metadata", {}).get("preference_tradeoffs", {})
    cards = []
    sources: Dict[str, Any] = {}
    review_records = {
        record.get("sku_id"): record
        for record in (turn.get("grounding_evidence") or {})
        .get("review_evidence", {})
        .get("records", [])
    }
    for product in ranked:
        review_record = review_records.get(product.get("sku_id"), {})
        review_themes = review_record.get("themes", {})
        review_theme = next(iter(review_themes.values()), None)
        reason_tags = selection.get("selection_reasons", {}).get(product.get("sku_id"), [])
        reasons = _selection_reason_labels(product, reason_tags)
        reasons.extend(_card_reasons(product, turn.get("preference_state", {})))
        reasons = list(dict.fromkeys(reasons))[:3]
        if review_theme and review_theme.get("sentiment") in {"positive", "mixed"}:
            reasons = reasons[:2] + [f"Review theme: {review_theme['summary']}"]
        represented_tradeoffs = tradeoffs_by_sku.get(product.get("sku_id"), [])
        tradeoff = "; ".join(item["label"] for item in represented_tradeoffs) or _card_tradeoff(product, ranked, turn.get("preference_state", {}))
        if review_theme and review_theme.get("sentiment") in {"mixed", "negative"}:
            tradeoff = review_theme["summary"]
        card = {
            "sku_id": product.get("sku_id"),
            "name": product.get("name"),
            "price": product.get("price"),
            "why_it_matches": reasons,
            "tradeoff": tradeoff,
            "service_indicator": (
                {
                    "label": "California haul-away",
                    "available": product.get("haul_away_CA_available"),
                }
                if service_relevant and "haul_away_CA_available" in product
                else None
            ),
        }
        cards.append(card)
        field_sources = {
            "sku_id": PRODUCT_FACT_SOURCE,
            "name": PRODUCT_FACT_SOURCE,
            "price": PRODUCT_FACT_SOURCE,
            "why_it_matches": {
                "product_facts": PRODUCT_FACT_SOURCE,
                "shopper_preferences": AUTHORITATIVE_SOURCES["conversational_preferences"],
                "selection_order": RANKING_SOURCE,
                "score_signal": SCORING_SOURCE,
            },
            "tradeoff": PRODUCT_FACT_SOURCE,
        }
        if card["service_indicator"] is not None:
            field_sources["service_indicator"] = SERVICE_SOURCE
        if review_theme:
            field_sources["why_it_matches"]["review_evidence"] = REVIEW_SOURCE
            if review_theme.get("sentiment") in {"mixed", "negative"}:
                field_sources["tradeoff"] = REVIEW_SOURCE
            turn["review_debug"]["appeared_in_cards"] = True
        sources[product.get("sku_id", "unknown")] = field_sources
    contract["products"] = cards
    contract["selection_mode"] = mode
    contract["primary_product_id"] = selection.get("primary_product_id")
    contract["grounding_sources"] = {"products": sources, "ordering": RANKING_SOURCE}
    return contract


def _comparison_candidates(state: Dict[str, Any]) -> List[str]:
    hard = state.get("hard_constraints", {})
    fields: List[str] = []
    for field in _relevant_dimensions(state):
        if field not in fields:
            fields.append(field)
    if hard.get("max_price") is not None and "price" not in fields:
        fields.append("price")
    if hard.get("size") is not None:
        fields.append("available_sizes")
    if hard.get("exclude_latex") is True:
        fields.append("contains_latex")
    if hard.get("require_CA_haul_away") is True:
        fields.append("haul_away_CA_available")
    for field in (
        "price",
        "firmness",
        "support",
        "cooling",
        "motion_isolation",
        "trial_days",
        "warranty_years",
        "contains_latex",
        "haul_away_CA_available",
    ):
        if field not in fields:
            fields.append(field)
    return fields


def _comparison_label(field: str) -> str:
    labels = {
        **DIMENSION_LABELS,
        "available_sizes": "Available sizes",
        "contains_latex": "Latex",
        "haul_away_CA_available": "California haul-away",
        "trial_days": "Trial",
        "warranty_years": "Warranty",
    }
    return labels[field]


def _comparison_table(turn: Dict[str, Any]) -> Dict[str, Any]:
    products = (turn.get("grounding_data") or {}).get("products", [])
    names = [product.get("name") for product in products]
    rows = []
    relevant = set(_relevant_dimensions(turn.get("preference_state", {})))
    hard = turn.get("preference_state", {}).get("hard_constraints", {})
    explicitly_relevant = set(relevant)
    if hard.get("max_price") is not None:
        explicitly_relevant.add("price")
    if hard.get("size") is not None:
        explicitly_relevant.add("available_sizes")
    if hard.get("exclude_latex") is True:
        explicitly_relevant.add("contains_latex")
    if hard.get("require_CA_haul_away") is True:
        explicitly_relevant.add("haul_away_CA_available")

    for field in _comparison_candidates(turn.get("preference_state", {})):
        raw_values = [product.get(field) for product in products]
        meaningful_difference = len({repr(value) for value in raw_values}) > 1
        if field not in explicitly_relevant and not meaningful_difference:
            continue
        source = SERVICE_SOURCE if field == "haul_away_CA_available" else PRODUCT_FACT_SOURCE
        label = _comparison_label(field)
        formatted_values = [_format_value(field, value) for value in raw_values]
        if field == "available_sizes" and hard.get("size"):
            requested_size = hard["size"]
            formatted_values = [
                "Available" if requested_size in (value or []) else "Not available"
                for value in raw_values
            ]
            size_label = {"twin_xl": "Twin XL", "cal_king": "Cal King"}.get(
                requested_size, requested_size.title()
            )
            label = f"{size_label} availability"
        rows.append(
            {
                "key": field,
                "label": label,
                "values": formatted_values,
                "source": source,
                "selection_reason": "shopper_priority_or_requirement" if field in explicitly_relevant else "meaningful_product_difference",
            }
        )
        if len(rows) == 6:
            break
    review = (turn.get("grounding_data") or {}).get("review_evidence")
    if review:
        topic = review.get("requested_topic")
        by_sku = {record.get("sku_id"): record for record in review.get("records", [])}
        if topic == "complaints":
            values = [", ".join(by_sku.get(product.get("sku_id"), {}).get("common_complaints", [])) or "Unknown" for product in products]
            label, key = "Common complaint", "review_complaints"
        elif topic == "praise":
            values = [", ".join(by_sku.get(product.get("sku_id"), {}).get("common_praise", [])) or "Unknown" for product in products]
            label, key = "What reviewers like", "review_praise"
        else:
            values = []
            for product in products:
                record = by_sku.get(product.get("sku_id"), {})
                themes = record.get("themes", {})
                theme = themes.get(topic) if topic not in (None, "general") else next(iter(themes.values()), None)
                values.append(theme.get("summary") if theme else "Unknown")
            label = f"{str(topic).replace('_', ' ').title()} feedback" if topic not in (None, "general") else "Review highlight"
            key = f"review_{topic or 'general'}"
        rows.insert(0, {"key": key, "label": label, "values": values, "source": REVIEW_SOURCE, "selection_reason": "explicit_review_question"})
        rows = rows[:6]
        turn["review_debug"]["appeared_in_comparison"] = True
    message = (
        f"Here’s the clearest side-by-side view of {names[0]} and {names[1]}."
        if len(names) >= 2
        else "I need two mattresses from this collection to make a useful comparison."
    )
    contract = _contract(
        "comparison_table",
        message,
        "compare intent with at least two resolved catalog products",
    )
    contract["products"] = [
        {"sku_id": product.get("sku_id"), "name": product.get("name")}
        for product in products
    ]
    contract["comparison"] = {"products": names, "rows": rows}
    contract["grounding_sources"] = {
        "product_identity": PRODUCT_FACT_SOURCE,
        "rows": {row["key"]: row["source"] for row in rows},
    }
    return contract


def _product_detail(turn: Dict[str, Any]) -> Dict[str, Any]:
    product = (turn.get("grounding_data") or {}).get("product") or {}
    fields = []
    for field in (
        "price",
        "firmness",
        "support",
        "cooling",
        "motion_isolation",
        "materials",
        "contains_latex",
        "available_sizes",
        "trial_days",
        "warranty_years",
        "haul_away_CA_available",
    ):
        if field in product:
            fields.append(
                {
                    "key": field,
                    "label": _comparison_label(field) if field != "materials" else "Materials",
                    "value": _format_value(field, product[field]),
                    "source": (
                        SERVICE_SOURCE
                        if field == "haul_away_CA_available"
                        else PRODUCT_FACT_SOURCE
                    ),
                }
            )
    contract = _contract(
        "product_detail",
        f"Here are the most useful details on {product.get('name')}." if product else "I couldn't find that mattress in this collection.",
        "single resolved product with a broad, information-rich detail request",
    )
    contract["products"] = [
        {
            "sku_id": product.get("sku_id"),
            "name": product.get("name"),
            "details": fields,
        }
    ] if product else []
    contract["grounding_sources"] = {
        "product": PRODUCT_FACT_SOURCE,
        "fields": {item["key"]: item["source"] for item in fields},
    }
    return contract


def _recovery_label(option: Dict[str, Any]) -> str:
    if option.get("type") == "relax_max_price":
        return f"Raise budget to ${option['proposed_value']:,.0f}"
    if option.get("type") == "remove_haul_away_requirement":
        return "Continue without haul-away"
    if option.get("type") == "remove_latex_exclusion":
        return "Include mattresses with latex"
    return "Use this option"


def _recovery_choices(turn: Dict[str, Any]) -> Dict[str, Any]:
    recovery = turn.get("recovery") or {}
    actions = []
    for option in recovery.get("options", []):
        actions.append(
            {
                "label": _recovery_label(option),
                "action": "approve_relaxation",
                "patch": deepcopy(option.get("state_patch", {})),
                "match_count": option.get("match_count"),
                "evidence": deepcopy(option),
            }
        )
    if recovery.get("requires_user_approval"):
        actions.append(
            {
                "label": "Keep my current requirements",
                "action": "reject_relaxation",
                "patch": {},
                "match_count": 0,
            }
        )
    contract = _contract(
        "recovery_choices",
        recovery.get("message", "I couldn't find an exact match."),
        "blocked or conflicting result with grounded recovery options",
    )
    contract["actions"] = actions
    contract["suggested_replies"] = [action["label"] for action in actions]
    contract["grounding_sources"] = {
        "message": "deterministic_phase_4b_recovery_analysis",
        "actions": "deterministic_phase_4b_recovery_analysis",
    }
    return contract


def _clarification_replies(message: str) -> List[str]:
    lowered = message.casefold()
    if any(term in lowered for term in ("current mattress", "bothers", "feel")):
        return [
            "It sleeps too hot",
            "I sink in too much",
            "It's too firm",
            "My partner's movement wakes me up",
        ]
    return []


def _conversation(turn: Dict[str, Any], reason: str) -> Dict[str, Any]:
    message = turn.get("response_text") or "How can I help with your mattress search?"
    contract = _contract("conversation", message, reason)
    if (turn.get("recovery") or {}).get("recovery_type") == "clarification":
        contract["elicitation"] = deepcopy(turn.get("pending_elicitation"))
        if contract["elicitation"] is None:
            contract["suggested_replies"] = _clarification_replies(message)
        contract["grounding_sources"] = {
            "message": AUTHORITATIVE_SOURCES["conversational_preferences"]
        }
    elif turn.get("grounding_data"):
        contract["grounding_sources"] = {
            "message": (turn["grounding_data"].get("authoritative_source") if isinstance(turn["grounding_data"], dict) else None)
        }
    return contract


def build_turn_presentation(turn: Dict[str, Any]) -> Dict[str, Any]:
    """Select a modality and build its framework-neutral presentation payload."""
    recovery = turn.get("recovery") or {}
    if recovery.get("options") and recovery.get("requires_user_approval"):
        return _recovery_choices(turn)

    if turn.get("response_strategy") == "clarification":
        return _conversation(turn, "clarification is best resolved through language")

    if turn.get("intent") == "compare":
        products = (turn.get("grounding_data") or {}).get("products", [])
        if len(products) >= 2:
            return _comparison_table(turn)
        return _conversation(turn, "comparison could not resolve two products")

    if turn.get("intent") == "product_question":
        grounding = turn.get("grounding_data") or {}
        if turn.get("response_strategy") == "review_evidence_lookup":
            return _conversation(turn, "a focused review question is best answered conversationally")
        if grounding.get("product") and grounding.get("attribute") is None:
            return _product_detail(turn)
        return _conversation(turn, "a single factual answer does not need structured UI")

    decision = turn.get("decision_result") or {}
    if turn.get("intent") == "recommend" and decision.get("decision") == "ALLOW":
        return _recommendation_cards(turn)

    return _conversation(turn, "the turn is most clearly answered in conversational prose")


def with_presentation_message(
    presentation: Dict[str, Any], message: str
) -> Dict[str, Any]:
    """Return a copy with generated conversational framing applied."""
    updated = deepcopy(presentation)
    updated["message"] = message
    return updated
