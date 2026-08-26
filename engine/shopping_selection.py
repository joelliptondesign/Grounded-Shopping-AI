"""Structured shopping judgment over deterministically eligible candidates."""

import json
import os
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv

from engine.decision import constraint_violations
from engine.model_config import ModelTask, model_configuration, responses_request_options
from engine.preference_extraction import _validate_schema_value
from engine.prompts import load_prompt


SELECTION_MODES = ("strong_recommendation", "exploratory_shortlist")
REASON_TAGS = (
    "strong_overall_fit",
    "strong_all_around_option",
    "good_use_of_budget",
    "good_value",
    "balanced_fit",
    "lower_price_option",
    "premium_option",
    "high_cooling",
    "strong_motion_isolation",
    "strong_support",
    "closest_firmness_fit",
    "useful_tradeoff_option",
)

SHOPPING_SELECTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "selection_mode": {"type": "string", "enum": list(SELECTION_MODES)},
        "primary_product_id": {"type": ["string", "null"]},
        "selections": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "reason_tags": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {"type": "string", "enum": list(REASON_TAGS)},
                    },
                },
                "required": ["product_id", "reason_tags"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["selection_mode", "primary_product_id", "selections"],
    "additionalProperties": False,
}

BASE_SELECTION_INSTRUCTION = load_prompt("shopping_selection.md")
RETRY_SELECTION_INSTRUCTION = (
    BASE_SELECTION_INSTRUCTION
    + "\n\nYour prior selection failed deterministic validation. Return only supplied "
    "eligible product IDs, use unique IDs, keep exploratory primary null, and make "
    "a strong primary equal the first selected product."
)


def _meaningful_non_price_signal(shopper_state: Dict[str, Any]) -> bool:
    priorities = shopper_state.get("priorities", {})
    directions = shopper_state.get("directions", {})
    soft = shopper_state.get("soft_preferences", {})
    for field in ("firmness", "support", "cooling", "motion_isolation"):
        if priorities.get(field) in {"high", "critical"}:
            return True
        if directions.get(field) is not None:
            return True
        if soft.get(f"{field}_target") is not None:
            return True
    return False


def deterministic_selection_fallback(
    decision_result: Dict[str, Any], shopper_state: Dict[str, Any]
) -> Dict[str, Any]:
    """Use scorer order safely when model selection is unavailable or invalid."""
    candidates = decision_result.get("ranked_candidates", [])[:3]
    if not candidates:
        return {
            "selection_mode": "exploratory_shortlist",
            "primary_product_id": None,
            "selections": [],
            "selected_product_ids": [],
            "selection_reasons": {},
            "validation": {"valid": True, "reasons": []},
            "fallback_used": True,
            "fallback_reason": "no_eligible_candidates",
        }
    strong = len(candidates) == 1 or _meaningful_non_price_signal(shopper_state)
    ids = [item["sku_id"] for item in candidates]
    reasons = {
        sku_id: (["strong_overall_fit"] if index == 0 else ["useful_tradeoff_option"])
        for index, sku_id in enumerate(ids)
    }
    return {
        "selection_mode": "strong_recommendation" if strong else "exploratory_shortlist",
        "primary_product_id": ids[0] if strong else None,
        "selections": [
            {"product_id": sku_id, "reason_tags": reasons[sku_id]} for sku_id in ids
        ],
        "selected_product_ids": ids,
        "selection_reasons": reasons,
        "validation": {"valid": True, "reasons": []},
        "fallback_used": True,
        "fallback_reason": "selection_generation_unavailable",
    }


def _supported_reason(
    tag: str,
    product: Dict[str, Any],
    selected: List[Dict[str, Any]],
    decision_preferences: Dict[str, Any],
) -> bool:
    if tag == "high_cooling":
        return isinstance(product.get("cooling"), (int, float)) and product["cooling"] >= 8
    if tag == "strong_motion_isolation":
        return isinstance(product.get("motion_isolation"), (int, float)) and product["motion_isolation"] >= 8
    if tag == "strong_support":
        return isinstance(product.get("support"), (int, float)) and product["support"] >= 8
    prices = [item.get("price") for item in selected if isinstance(item.get("price"), (int, float))]
    if tag == "lower_price_option":
        return bool(prices) and product.get("price") == min(prices)
    if tag == "premium_option":
        return bool(prices) and product.get("price") == max(prices)
    if tag == "good_use_of_budget":
        price = product.get("price")
        target = decision_preferences.get("budget_target")
        upper = decision_preferences.get("budget_flex_max") or decision_preferences.get("max_price")
        if not isinstance(price, (int, float)) or not isinstance(target, (int, float)):
            return False
        if isinstance(upper, (int, float)) and price > upper:
            return False
        # This tag describes fit with the stated spending range relative to the
        # represented choices, not cheapness. A lower-priced outlier can still
        # be represented with value/lower-price language.
        return price > min(prices) or price >= target * 0.75
    return True


def validate_shopping_selection(
    selection: Dict[str, Any],
    eligible_candidates: Iterable[Dict[str, Any]],
    decision_preferences: Dict[str, Any],
) -> Dict[str, Any]:
    reasons: List[str] = []
    try:
        _validate_schema_value(selection, SHOPPING_SELECTION_SCHEMA, "shopping_selection")
    except ValueError as error:
        return {"valid": False, "reasons": [f"schema:{error}"]}

    eligible = {item.get("sku_id"): item for item in eligible_candidates}
    ids = [item["product_id"] for item in selection["selections"]]
    if not 1 <= len(ids) <= 3:
        reasons.append("invalid_selection_count")
    if any(not 1 <= len(item["reason_tags"]) <= 3 for item in selection["selections"]):
        reasons.append("invalid_reason_count")
    if len(ids) != len(set(ids)):
        reasons.append("duplicate_product_id")
    for product_id in ids:
        if product_id not in eligible:
            reasons.append(f"product_not_eligible:{product_id}")
            continue
        violations = constraint_violations(decision_preferences, eligible[product_id])
        if violations:
            reasons.append(f"hard_constraint_violation:{product_id}")
    primary = selection["primary_product_id"]
    if selection["selection_mode"] == "strong_recommendation":
        if primary is None or not ids or primary != ids[0]:
            reasons.append("invalid_strong_primary")
    elif primary is not None:
        reasons.append("exploratory_primary_must_be_null")
    if primary is not None and primary not in ids:
        reasons.append("primary_not_selected")
    selected = [eligible[item] for item in ids if item in eligible]
    for item in selection["selections"]:
        product = eligible.get(item["product_id"])
        if product:
            for tag in item["reason_tags"]:
                if not _supported_reason(tag, product, selected, decision_preferences):
                    reasons.append(f"unsupported_reason:{item['product_id']}:{tag}")
    return {"valid": not reasons, "reasons": list(dict.fromkeys(reasons))}


def _normalized_selection(selection: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
    output = deepcopy(selection)
    output["selected_product_ids"] = [item["product_id"] for item in output["selections"]]
    output["selection_reasons"] = {
        item["product_id"]: item["reason_tags"] for item in output["selections"]
    }
    output["validation"] = validation
    output["fallback_used"] = False
    output["fallback_reason"] = None
    return output


def _normalize_single_eligible_candidate(
    selection: Dict[str, Any], eligible_candidates: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    """Present the sole safe ALLOW candidate as a singular recommendation."""
    eligible_ids = [item.get("sku_id") for item in eligible_candidates if item.get("sku_id")]
    output = deepcopy(selection)
    if len(eligible_ids) == 1 and [item["product_id"] for item in output["selections"]] == eligible_ids:
        output["selection_mode"] = "strong_recommendation"
        output["primary_product_id"] = eligible_ids[0]
    return output


def select_shopping_products(
    decision_result: Dict[str, Any],
    shopper_state: Dict[str, Any],
    decision_preferences: Dict[str, Any],
    current_message: str,
    *,
    conversation_history: Optional[Iterable[Dict[str, str]]] = None,
    recent_product_names: Optional[Iterable[str]] = None,
    review_evidence: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Generate, validate, and once retry the authoritative shopper-facing selection."""
    candidates = decision_result.get("ranked_candidates", [])
    if decision_result.get("decision") != "ALLOW" or not candidates:
        return deterministic_selection_fallback(decision_result, shopper_state)
    if client is None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return deterministic_selection_fallback(decision_result, shopper_state)
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

    scores = {
        item.get("sku_id"): item for item in decision_result.get("metadata", {}).get("candidate_scores", [])
    }
    payload = {
        "current_shopper_message": current_message,
        "shopper_state": deepcopy(shopper_state),
        "recent_conversation": list(conversation_history or [])[-8:],
        "recently_shown_or_referenced_products": list(recent_product_names or []),
        "eligible_candidates": [
            {
                **deepcopy(candidate),
                "deterministic_score_signal": scores.get(candidate.get("sku_id"), {}).get("score"),
                "deterministic_rank_signal": scores.get(candidate.get("sku_id"), {}).get("current_rank"),
                "represented_tradeoffs": deepcopy(
                    decision_result.get("metadata", {}).get("preference_tradeoffs", {}).get(candidate.get("sku_id"), [])
                ),
            }
            for candidate in candidates
        ],
        "represented_review_evidence": deepcopy(review_evidence or {}),
    }
    config = model_configuration(ModelTask.CONVERSATIONAL_REASONING, model_override=model)
    failures = []
    for attempt, instruction in enumerate(
        (BASE_SELECTION_INSTRUCTION, RETRY_SELECTION_INSTRUCTION), start=1
    ):
        try:
            response = client.responses.create(
                **responses_request_options(config),
                input=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "shopping_product_selection",
                        "schema": SHOPPING_SELECTION_SCHEMA,
                        "strict": True,
                    }
                },
            )
            selection = json.loads(response.output_text)
            selection = _normalize_single_eligible_candidate(selection, candidates)
            validation = validate_shopping_selection(
                selection, candidates, decision_preferences
            )
        except Exception as error:
            failures.append({"attempt": attempt, "reasons": [type(error).__name__]})
            continue
        failures.append({"attempt": attempt, "reasons": validation["reasons"]})
        if validation["valid"]:
            output = _normalized_selection(selection, validation)
            output["attempts"] = failures
            return output
    fallback = deterministic_selection_fallback(decision_result, shopper_state)
    fallback["fallback_reason"] = "selection_validation_failed"
    fallback["attempts"] = failures
    return fallback
