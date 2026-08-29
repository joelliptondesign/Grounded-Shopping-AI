"""Grounding contracts and deterministic validation for customer-facing claims."""

import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional


AUTHORITATIVE_SOURCES = {
    "product_facts": "structured_catalog_fixture",
    "service_eligibility": "structured_service_fixture_and_eligibility_logic",
    "recommendation": "validated_shopping_agent_selection",
    "candidate_ranking": "deterministic_eligibility_and_scoring_result",
    "conversational_preferences": "validated_structured_conversational_state",
    "review_evidence": "precomputed_customer_review_evidence_fixture_v2",
}

EXPECTED_PRODUCT_FACTS = (
    "price",
    "available_sizes",
    "firmness",
    "support",
    "cooling",
    "motion_isolation",
    "materials",
    "contains_latex",
    "trial_days",
    "warranty_years",
)

UNSUPPORTED_CAPABILITY_PATTERNS = {
    "live_inventory": re.compile(
        r"\b(?:checked|checking|check)\s+(?:the\s+)?live inventory\b|"
        r"\blive (?:amazon )?inventory\b|\breal-time inventory\b",
        re.IGNORECASE,
    ),
    "live_pricing": re.compile(
        r"\b(?:checked|checking)\s+(?:the\s+)?live pric(?:e|ing)\b|"
        r"\blive pric(?:e|ing)\b|\breal-time pric(?:e|ing)\b",
        re.IGNORECASE,
    ),
    "reviews": re.compile(
        r"\b(?:analy(?:zed|sing)|searched|scraped)\b[^.!?]{0,80}"
        r"\b(?:customer |verified )?reviews?\b|\bthousands of (?:customer )?reviews\b",
        re.IGNORECASE,
    ),
    "live_fulfillment": re.compile(
        r"\blive fulfillment\b|\breal-time fulfillment\b|"
        r"\b(?:checked|checking)\b[^.!?]{0,50}\bfulfillment\b",
        re.IGNORECASE,
    ),
}

RECOMMENDATION_TERMS = re.compile(
    r"\b(?:recommend(?:ed|ation)?|top match|best (?:match|choice|option)|"
    r"selected (?:result|mattress|option)|my pick|go with|choose)\b",
    re.IGNORECASE,
)
RELAXATION_TERMS = re.compile(
    r"\b(?:relax(?:ed|ing)?|ignore[sd]?|waive[sd]?|override[sd]?|"
    r"set aside|went above|exceed(?:ed|s|ing)?)\b",
    re.IGNORECASE,
)


def _known_product_facts(product: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not product:
        return {}
    return {
        key: deepcopy(value)
        for key, value in product.items()
        if key != "haul_away_CA_available"
    }


def build_recommendation_evidence(
    decision_result: Dict[str, Any],
    structured_preferences: Dict[str, Any],
    *,
    shopping_selection: Optional[Dict[str, Any]] = None,
    approved_relaxation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct the only product, service, and selection facts prose may use."""
    ranked = decision_result.get("ranked_candidates", [])
    by_id = {item.get("sku_id"): item for item in ranked}
    deterministic_selected = decision_result.get("selected_sku")
    if deterministic_selected and deterministic_selected.get("sku_id"):
        by_id.setdefault(deterministic_selected["sku_id"], deterministic_selected)
    selection = shopping_selection or {}
    selected_ids = selection.get("selected_product_ids") or (
        [deterministic_selected.get("sku_id")] if deterministic_selected else []
    )
    presented = [by_id[sku_id] for sku_id in selected_ids if sku_id in by_id]
    primary_id = selection.get("primary_product_id")
    selected = by_id.get(primary_id) if primary_id else (presented[0] if presented else None)
    metadata = decision_result.get("metadata", {})
    service_verified = bool(
        selected is not None and selected.get("haul_away_CA_available") is not None
    )
    verified_product_facts = [
        field
        for field in EXPECTED_PRODUCT_FACTS
        if selected and selected.get(field) is not None
    ]
    unknown_product_facts = [
        field
        for field in EXPECTED_PRODUCT_FACTS
        if not selected or selected.get(field) is None
    ]
    active_constraints = deepcopy(metadata.get("active_hard_constraints", {}))
    return {
        "intent": "recommend",
        "authoritative_sources": deepcopy(AUTHORITATIVE_SOURCES),
        "decision": decision_result.get("decision"),
        "decision_reason": decision_result.get("reason"),
        "selected_sku": _known_product_facts(selected) if selected else None,
        "presented_skus": [_known_product_facts(item) for item in presented],
        "shopping_selection": deepcopy(selection),
        "selection_mode": selection.get("selection_mode", "strong_recommendation"),
        "primary_product_id": primary_id,
        "match_type": decision_result.get("match_type"),
        "preference_tradeoffs": deepcopy(metadata.get("preference_tradeoffs", {})),
        "fact_status": {
            "verified_product_facts": verified_product_facts,
            "unknown_product_facts": unknown_product_facts,
            "verified_service_facts": ["CA_haul_away"] if service_verified else [],
            "unknown_service_facts": [] if service_verified else ["CA_haul_away"],
        },
        "ranking_context": {
            "selected_sku_id": selected.get("sku_id") if selected else None,
            "agent_selected_product_ids": selected_ids,
            "deterministic_top_sku_id": (
                (deterministic_selected or {}).get("sku_id")
            ),
            "active_normalized_weights": deepcopy(
                metadata.get("active_normalized_weights", {})
            ),
            "candidate_count": metadata.get("candidate_count", 0),
            "previous_selected_sku_id": metadata.get("previous_selected_sku_id"),
        },
        "verified_services": {
            "CA_haul_away": {
                "verified": service_verified,
                "available": (
                    selected.get("haul_away_CA_available")
                    if service_verified
                    else None
                ),
            }
        },
        "structured_preferences": deepcopy(structured_preferences),
        "hard_constraints": active_constraints,
        "constraint_relaxation": {
            "approved": approved_relaxation is not None,
            "applied_change": deepcopy(approved_relaxation),
            "active_constraints_are_authoritative": True,
        },
        "blocked_violations": deepcopy(decision_result.get("violations", [])),
    }


def known_product_references(
    catalog: Iterable[Dict[str, Any]],
) -> List[Dict[str, str]]:
    return [
        {"sku_id": str(item.get("sku_id", "")), "name": str(item.get("name", ""))}
        for item in catalog
        if item.get("sku_id") or item.get("name")
    ]


def _sentences(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _validate_represented_facts(
    text: str, evidence: Dict[str, Any]
) -> List[str]:
    """Check high-risk factual forms against the represented selected records."""
    reasons: List[str] = []
    selected = evidence.get("selected_sku") or {}
    presented = evidence.get("presented_skus") or ([selected] if selected else [])
    preferences = evidence.get("structured_preferences") or {}
    allowed_money = {
        int(value)
        for value in (
            *(item.get("price") for item in presented),
            preferences.get("max_price"),
            preferences.get("budget_target"),
            preferences.get("budget_flex_max"),
        )
        if isinstance(value, (int, float))
    }
    for tradeoffs in evidence.get("preference_tradeoffs", {}).values():
        for tradeoff in tradeoffs:
            if isinstance(tradeoff.get("amount"), (int, float)):
                allowed_money.add(int(tradeoff["amount"]))
    for raw_value in re.findall(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text):
        value = int(float(raw_value.replace(",", "")))
        if value not in allowed_money:
            reasons.append("unverified_product_fact:price")

    for field in ("firmness", "support", "cooling", "motion_isolation"):
        label = field.replace("_", r"[\s_-]+")
        for match in re.finditer(
            rf"\b{label}\b[^.!?\d]{{0,20}}(\d+(?:\.\d+)?)\s*(?:/\s*10)?",
            text,
            re.IGNORECASE,
        ):
            stated = float(match.group(1))
            represented_values = {
                float(item[field])
                for item in presented
                if isinstance(item.get(field), (int, float))
            }
            if stated not in represented_values:
                reasons.append(f"unverified_product_fact:{field}")

    lowered = text.casefold()
    if "latex" in lowered:
        latex_values = {
            item.get("contains_latex")
            for item in presented
            if item.get("contains_latex") in (True, False)
        }
        if not latex_values:
            reasons.append("unverified_product_fact:contains_latex")
        else:
            negative = bool(
                re.search(r"\b(?:latex[- ]free|no latex|does not contain latex|without latex)\b", lowered)
            )
            positive = bool(re.search(r"\bcontains latex\b", lowered))
            if negative and False not in latex_values:
                reasons.append("product_fact_mismatch:contains_latex")
            if positive and True not in latex_values:
                reasons.append("product_fact_mismatch:contains_latex")

    service = evidence.get("verified_services", {}).get("CA_haul_away", {})
    if re.search(r"\bhaul[- ]away\b", lowered):
        if not service.get("verified"):
            reasons.append("unverified_service_fact:CA_haul_away")
        else:
            unavailable = bool(re.search(r"\b(?:not|isn't) available\b", lowered))
            available = bool(
                re.search(r"\b(?:is |listed as |currently )?available\b|\bqualif(?:y|ies)\b", lowered)
            ) and not unavailable
            if unavailable and service.get("available") is True:
                reasons.append("service_fact_mismatch:CA_haul_away")
            if available and service.get("available") is False:
                reasons.append("service_fact_mismatch:CA_haul_away")

    return reasons


def validate_recommendation_text(
    text: str,
    evidence: Dict[str, Any],
    known_products: Iterable[Dict[str, str]],
    *,
    structured_product_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Validate winner identity, blocked state, capabilities, and constraints.

    Product identity may be supplied by a validated structured presentation that
    is delivered with the prose. Factual claims made in prose remain subject to
    the same represented-fact and recommendation-authority checks.
    """
    reasons: List[str] = []
    lowered = text.casefold()
    decision = evidence.get("decision")
    selected = evidence.get("selected_sku") or {}
    selected_id = str(selected.get("sku_id", ""))
    selected_name = str(selected.get("name", ""))
    presented = evidence.get("presented_skus") or ([selected] if selected else [])
    authoritative_ids = (
        evidence.get("shopping_selection", {}).get("selected_product_ids")
        or ([selected_id] if selected_id else [])
    )
    represented_ids = {str(item) for item in authoritative_ids}
    structured_ids = {str(item) for item in (structured_product_ids or [])}
    selection_presented_in_ui = bool(represented_ids) and represented_ids.issubset(
        structured_ids
    )
    represented_names = {
        str(item.get("name", "")).casefold() for item in presented if item.get("name")
    }

    for capability, pattern in UNSUPPORTED_CAPABILITY_PATTERNS.items():
        if pattern.search(text):
            reasons.append(f"unsupported_capability:{capability}")
    reasons.extend(_validate_represented_facts(text, evidence))
    if evidence.get("review_evidence"):
        reasons.extend(validate_review_text(text, evidence["review_evidence"])["reasons"])

    if decision == "ALLOW":
        mode = evidence.get("selection_mode", "strong_recommendation")
        if not selection_presented_in_ui and mode == "strong_recommendation" and (
            not selected_name or selected_name.casefold() not in lowered
        ):
            reasons.append("selected_product_not_named")
        if not selection_presented_in_ui and mode == "exploratory_shortlist" and represented_names and not any(
            name in lowered for name in represented_names
        ):
            reasons.append("selected_product_not_named")

        for sentence in _sentences(text):
            if not RECOMMENDATION_TERMS.search(sentence):
                continue
            sentence_lower = sentence.casefold()
            for product in known_products:
                product_id = product.get("sku_id", "")
                product_name = product.get("name", "")
                if product_id in represented_ids:
                    continue
                if (
                    product_name
                    and product_name.casefold() in sentence_lower
                    or product_id
                    and re.search(rf"\b{re.escape(product_id.casefold())}\b", sentence_lower)
                ):
                    reasons.append(f"different_product_recommended:{product_id}")

        if RELAXATION_TERMS.search(text) and not evidence.get(
            "constraint_relaxation", {}
        ).get("approved"):
            reasons.append("unapproved_constraint_relaxation")
    elif decision == "BLOCK":
        if RECOMMENDATION_TERMS.search(text):
            reasons.append("blocked_outcome_presented_as_recommendation")
        for product in known_products:
            name = product.get("name", "")
            if name and name.casefold() in lowered:
                reasons.append("blocked_outcome_names_product")
                break
    else:
        reasons.append("unsupported_decision_state")

    reasons = list(dict.fromkeys(reasons))
    return {"valid": not reasons, "reasons": reasons}


REVIEW_TOPIC_TERMS = {
    "cooling": ("cool", "cooling", "hot", "warm", "temperature", "heat"),
    "motion_isolation": ("motion", "movement transfer", "partner disturbance"),
    "firmness": ("firm", "soft", "hard", "feel"),
    "contouring": ("contour", "sink", "hug", "pressure relief"),
    "ease_of_movement": ("reposition", "change positions", "easy to move", "movement"),
    "value": ("value", "for the price", "afford"),
    "durability": ("durab", "sag", "impression", "softening", "held up"),
    "setup_odor": ("odor", "smell", "off-gas", "setup", "unboxing"),
    "edge_support": ("edge support", "edge", "perimeter"),
}


def validate_review_text(text: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Reject high-risk review claims not represented in the supplied slice."""
    reasons: List[str] = []
    lowered = text.casefold()
    records = evidence.get("records", [])
    represented_topics = {
        topic for record in records for topic in record.get("themes", {})
    }
    unknown_topics = {item.get("topic") for item in evidence.get("unknown_topics", [])}

    if re.search(r"(?:reviewer|owner|customer)\s+(?:said|wrote|called it)\s*[,:]?\s*[\"“']", text, re.IGNORECASE):
        reasons.append("unsupported_verbatim_review_quote")
    if re.search(r"\b(?:currently|right now|today)\b[^.!?]{0,40}\b(?:rated|reviews?|ratings?)\b", lowered):
        reasons.append("unsupported_live_review_claim")

    allowed_counts = {str(record["review_count"]) for record in records if "review_count" in record}
    for count in re.findall(r"\b([0-9][0-9,]*)\s+(?:customer\s+)?reviews?\b", text, re.IGNORECASE):
        if count.replace(",", "") not in allowed_counts:
            reasons.append("unverified_review_count")
    allowed_ratings = {str(record["average_rating"]) for record in records if "average_rating" in record}
    for rating in re.findall(r"\b(\d(?:\.\d)?)\s*(?:/\s*5|stars?)\b", text, re.IGNORECASE):
        if rating not in allowed_ratings:
            reasons.append("unverified_average_rating")

    review_markers = re.search(r"\b(?:reviewers?|owners?|customers?|feedback|reviews?)\b", lowered)
    if review_markers:
        topic_text = lowered
        product_names = list(evidence.get("requested_products", []))
        product_names.extend(evidence.get("product_names", {}).values())
        product_names.extend(
            item.get("name", "") for item in evidence.get("catalog_context", [])
        )
        for product_name in product_names:
            topic_text = topic_text.replace(str(product_name).casefold(), " ")
        for topic, terms in REVIEW_TOPIC_TERMS.items():
            if any(term in topic_text for term in terms) and topic not in represented_topics:
                # An explicit unknown topic may only be described as unknown.
                if topic in unknown_topics and re.search(r"\b(?:don't|do not|not enough|unavailable|unknown)\b", lowered):
                    continue
                reasons.append(f"unrepresented_review_theme:{topic}")
    catalog_context = evidence.get("catalog_context", [])
    represented_catalog_fields = {
        key
        for item in catalog_context
        for key in item
        if key not in {"sku_id", "name"}
    }
    catalog_terms = {
        "price": ("price", "$"),
        "contains_latex": ("latex",),
        "available_sizes": ("size", "queen", "king", "twin", "full"),
        "trial_days": ("trial",),
        "warranty_years": ("warranty",),
        "haul_away_CA_available": ("haul-away", "haul away"),
    }
    if review_markers or evidence.get("requested_topic"):
        for field, terms in catalog_terms.items():
            if field not in represented_catalog_fields and any(term in lowered for term in terms):
                reasons.append(f"unrepresented_catalog_claim:{field}")
    reasons = list(dict.fromkeys(reasons))
    return {"valid": not reasons, "reasons": reasons}
