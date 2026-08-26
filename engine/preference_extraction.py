"""Schema-constrained extraction of conversational mattress preferences.

The language model is limited to interpretation and state updates. Eligibility,
ranking, and selection remain the responsibility of ``engine.decision``.
"""

import json
import os
from copy import deepcopy
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from engine.prompts import load_prompt
from engine.model_config import (
    ModelTask,
    model_configuration,
    responses_request_options,
)


PRIORITY_LEVELS = ("low", "medium", "high", "critical")
INTENTS = ("recommend", "compare", "product_question", "service_question", "off_topic")
SHOPPING_ACTIONS = (
    "recommend_products",
    "compare_products",
    "choose_from_products",
    "answer_product_question",
    "answer_service_question",
    "off_topic",
    "clarify_reference",
)
RECOVERY_RESPONSES = ("none", "approve", "reject")
DIRECTIONS = ("higher", "lower")
RECOMMENDATION_READINESS_LEVELS = ("low", "exploratory", "strong")
CLARIFICATION_REASONS = (
    "cold_start_basics",
    "blocking_ambiguity",
    "reference_ambiguity",
    "other",
)
PRODUCT_ATTRIBUTES = (
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
    "unknown",
)
INFORMATION_SOURCES = ("catalog", "reviews")
REVIEW_TOPICS = (
    "general",
    "cooling",
    "motion_isolation",
    "firmness",
    "contouring",
    "ease_of_movement",
    "value",
    "durability",
    "setup_odor",
    "praise",
    "complaints",
    "edge_support",
    "unknown",
)

PREFERENCE_UPDATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "shopping_action": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": list(SHOPPING_ACTIONS)},
                "product_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "product_attribute": {
                    "type": ["string", "null"],
                    "enum": [*PRODUCT_ATTRIBUTES, None],
                },
                "service_attribute": {
                    "type": ["string", "null"],
                    "enum": ["haul_away", "unknown", None],
                },
            },
            "required": [
                "action",
                "product_ids",
                "product_attribute",
                "service_attribute",
            ],
            "additionalProperties": False,
        },
        "turn_context": {
            "type": "object",
            "properties": {
                "product_names": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "product_attribute": {
                    "type": ["string", "null"],
                    "enum": [*PRODUCT_ATTRIBUTES, None],
                },
                "service_attribute": {
                    "type": ["string", "null"],
                    "enum": ["haul_away", "unknown", None],
                },
                "exact_product_request": {"type": "boolean"},
                "information_source": {
                    "type": ["string", "null"],
                    "enum": [*INFORMATION_SOURCES, None],
                },
                "review_topic": {
                    "type": ["string", "null"],
                    "enum": [*REVIEW_TOPICS, None],
                },
                "explicit_browse_intent": {"type": "boolean"},
            },
            "required": [
                "product_names",
                "product_attribute",
                "service_attribute",
                "exact_product_request",
                "information_source",
                "review_topic",
                "explicit_browse_intent",
            ],
            "additionalProperties": False,
        },
        "recovery_response": {
            "type": "string",
            "enum": list(RECOVERY_RESPONSES),
        },
        "hard_constraints": {
            "type": "object",
            "properties": {
                "size": {
                    "type": ["string", "null"],
                    "enum": ["twin", "twin_xl", "full", "queen", "king", "cal_king", None],
                },
                "max_price": {"type": ["number", "null"], "minimum": 0},
                "exclude_latex": {"type": ["boolean", "null"]},
                "require_CA_haul_away": {"type": ["boolean", "null"]},
            },
            "required": ["size", "max_price", "exclude_latex", "require_CA_haul_away"],
            "additionalProperties": False,
        },
        "soft_preferences": {
            "type": "object",
            "properties": {
                "budget_target": {"type": ["number", "null"], "minimum": 0},
                "budget_flex_max": {"type": ["number", "null"], "minimum": 0},
                "prefer_CA_haul_away": {"type": ["boolean", "null"]},
                "firmness_target": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
                "support_target": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
                "cooling_target": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
                "motion_isolation_target": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": [
                "budget_target",
                "budget_flex_max",
                "prefer_CA_haul_away",
                "firmness_target",
                "support_target",
                "cooling_target",
                "motion_isolation_target",
            ],
            "additionalProperties": False,
        },
        "directions": {
            "type": "object",
            "properties": {
                "price": {"type": ["string", "null"], "enum": [*DIRECTIONS, None]},
                "firmness": {"type": ["string", "null"], "enum": [*DIRECTIONS, None]},
                "support": {"type": ["string", "null"], "enum": [*DIRECTIONS, None]},
                "cooling": {"type": ["string", "null"], "enum": [*DIRECTIONS, None]},
                "motion_isolation": {"type": ["string", "null"], "enum": [*DIRECTIONS, None]},
            },
            "required": ["price", "firmness", "support", "cooling", "motion_isolation"],
            "additionalProperties": False,
        },
        "priorities": {
            "type": "object",
            "properties": {
                "price": {"type": ["string", "null"], "enum": [*PRIORITY_LEVELS, None]},
                "firmness": {"type": ["string", "null"], "enum": [*PRIORITY_LEVELS, None]},
                "support": {"type": ["string", "null"], "enum": [*PRIORITY_LEVELS, None]},
                "cooling": {"type": ["string", "null"], "enum": [*PRIORITY_LEVELS, None]},
                "motion_isolation": {
                    "type": ["string", "null"],
                    "enum": [*PRIORITY_LEVELS, None],
                },
            },
            "required": ["price", "firmness", "support", "cooling", "motion_isolation"],
            "additionalProperties": False,
        },
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "clarification_reason": {
            "type": ["string", "null"],
            "enum": [*CLARIFICATION_REASONS, None],
        },
        "recommendation_readiness": {
            "type": "string",
            "enum": list(RECOMMENDATION_READINESS_LEVELS),
        },
    },
    "required": [
        "intent",
        "shopping_action",
        "turn_context",
        "recovery_response",
        "hard_constraints",
        "soft_preferences",
        "directions",
        "priorities",
        "needs_clarification",
        "clarification_question",
        "clarification_reason",
        "recommendation_readiness",
    ],
    "additionalProperties": False,
}


EMPTY_STATE: Dict[str, Any] = {
    "intent": None,
    "hard_constraints": {
        "size": None,
        "max_price": None,
        "exclude_latex": None,
        "require_CA_haul_away": None,
    },
    "soft_preferences": {
        "budget_target": None,
        "budget_flex_max": None,
        "prefer_CA_haul_away": None,
        "firmness_target": None,
        "support_target": None,
        "cooling_target": None,
        "motion_isolation_target": None,
    },
    "directions": {
        "price": None,
        "firmness": None,
        "support": None,
        "cooling": None,
        "motion_isolation": None,
    },
    "priorities": {
        "price": None,
        "firmness": None,
        "support": None,
        "cooling": None,
        "motion_isolation": None,
    },
    "needs_clarification": False,
    "clarification_question": None,
    "clarification_reason": None,
    "recommendation_readiness": "low",
    "pending_elicitation": None,
    "pending_recovery": None,
    "recent_product_names": [],
    "recent_presentations": [],
}


SYSTEM_PROMPT = load_prompt("preference_extraction.md")


def _inferred_recommendation_readiness(
    current_state: Optional[Dict[str, Any]], update: Dict[str, Any]
) -> str:
    """Compatibility fallback for fixtures that predate semantic readiness."""
    state = deepcopy(current_state or EMPTY_STATE)
    for section in ("hard_constraints", "soft_preferences", "directions", "priorities"):
        for key, value in update.get(section, {}).items():
            if value is not None:
                state.setdefault(section, {})[key] = value
    hard = state.get("hard_constraints", {})
    soft = state.get("soft_preferences", {})
    has_size = hard.get("size") is not None
    has_budget = any(
        value is not None
        for value in (
            hard.get("max_price"),
            soft.get("budget_target"),
            soft.get("budget_flex_max"),
        )
    )
    meaningful = sum(
        1
        for field in ("firmness", "support", "cooling", "motion_isolation")
        if state.get("directions", {}).get(field) is not None
        or state.get("priorities", {}).get(field) is not None
        or soft.get(f"{field}_target") is not None
    )
    if has_size and has_budget and meaningful:
        return "strong"
    if has_size or has_budget or meaningful:
        return "exploratory"
    return "low"


def new_preference_state() -> Dict[str, Any]:
    """Return an independent empty conversation state."""
    return deepcopy(EMPTY_STATE)


def extract_preference_update(
    user_message: str,
    current_state: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
    client: Optional[Any] = None,
    conversation_history: Optional[Any] = None,
    recent_results: Optional[Any] = None,
) -> Dict[str, Any]:
    """Use Structured Outputs to extract changes expressed in one user turn."""
    if not user_message or not user_message.strip():
        raise ValueError("user_message must not be empty")

    load_dotenv()
    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    payload = {
        "current_state": deepcopy(current_state or EMPTY_STATE),
        "recent_conversation": list(conversation_history or [])[-8:],
        "recent_presentation_results": deepcopy(recent_results or {}),
        "latest_user_message": user_message,
    }
    config = model_configuration(
        ModelTask.STRUCTURED_UNDERSTANDING, model_override=model
    )
    response = client.responses.create(
        **responses_request_options(config),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "mattress_preference_update",
                "schema": PREFERENCE_UPDATE_SCHEMA,
                "strict": True,
            }
        },
    )
    update = json.loads(response.output_text)
    if isinstance(update, dict):
        update.setdefault(
            "turn_context",
            {
                "product_names": [],
                "product_attribute": None,
                "service_attribute": None,
                "exact_product_request": False,
                "information_source": None,
                "review_topic": None,
            },
        )
        update["turn_context"].setdefault("exact_product_request", False)
        update["turn_context"].setdefault("information_source", None)
        update["turn_context"].setdefault("review_topic", None)
        update["turn_context"].setdefault("explicit_browse_intent", False)
        update.setdefault("recovery_response", "none")
        update.setdefault("directions", deepcopy(EMPTY_STATE["directions"]))
        update.setdefault("soft_preferences", {})
        update["soft_preferences"].setdefault("budget_flex_max", None)
        update["soft_preferences"].setdefault("prefer_CA_haul_away", None)
        # Compatibility for pre-4B mocked turn fixtures; the live strict schema
        # always supplies an intent.
        if update.get("intent") is None:
            update["intent"] = "recommend"
        update.setdefault(
            "recommendation_readiness",
            _inferred_recommendation_readiness(current_state, update),
        )
        update.setdefault(
            "clarification_reason",
            "blocking_ambiguity" if update.get("needs_clarification") else None,
        )
        if not isinstance(update.get("shopping_action"), dict):
            context = update["turn_context"]
            action_by_intent = {
                "compare": "compare_products",
                "product_question": "answer_product_question",
                "service_question": "answer_service_question",
                "off_topic": "off_topic",
            }
            action = action_by_intent.get(update["intent"], "recommend_products")
            if update["intent"] == "recommend" and len(context["product_names"]) >= 2:
                action = "choose_from_products"
            update["shopping_action"] = {
                "action": action,
                "product_ids": list(context["product_names"]),
                "product_attribute": context["product_attribute"],
                "service_attribute": context["service_attribute"],
            }
    validate_preference_update(update)
    return update


def validate_preference_update(update: Dict[str, Any]) -> None:
    """Reject malformed model output before it can alter valid state."""
    _validate_schema_value(update, PREFERENCE_UPDATE_SCHEMA, "preference_update")


def _validate_schema_value(value: Any, schema: Dict[str, Any], path: str) -> None:
    """Validate the JSON Schema subset used by the extraction boundary."""
    allowed_types = schema.get("type")
    if isinstance(allowed_types, str):
        allowed_types = [allowed_types]
    if allowed_types:
        matches_type = any(_matches_json_type(value, item) for item in allowed_types)
        if not matches_type:
            raise ValueError(f"{path} has an invalid type")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} has an unsupported value")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{path} is below its minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path} is above its maximum")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])).difference(value)
        if missing:
            raise ValueError(f"{path} is missing required fields")
        if schema.get("additionalProperties") is False:
            unexpected = set(value).difference(properties)
            if unexpected:
                raise ValueError(f"{path} contains unexpected fields")
        for key, child in value.items():
            if key in properties:
                _validate_schema_value(child, properties[key], f"{path}.{key}")

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_schema_value(item, schema["items"], f"{path}[{index}]")


def _matches_json_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def merge_preference_state(
    current_state: Optional[Dict[str, Any]],
    update: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge a sparse turn-level update into persistent conversation state."""
    merged = deepcopy(EMPTY_STATE)
    if current_state:
        for key, value in current_state.items():
            if key in ("hard_constraints", "soft_preferences", "directions", "priorities"):
                merged[key].update(deepcopy(value))
            else:
                merged[key] = deepcopy(value)

    if update.get("intent") is not None:
        merged["intent"] = update["intent"]

    for section in ("hard_constraints", "soft_preferences", "directions"):
        for key, value in update.get(section, {}).items():
            if value is not None:
                merged[section][key] = value

    for key, value in update.get("priorities", {}).items():
        if value is not None:
            merged["priorities"][key] = value

    merged["needs_clarification"] = bool(update.get("needs_clarification", False))
    merged["clarification_question"] = update.get("clarification_question")
    merged["clarification_reason"] = update.get("clarification_reason")
    merged["recommendation_readiness"] = update.get(
        "recommendation_readiness",
        _inferred_recommendation_readiness(current_state, update),
    )
    return merged


def extract_preference_state(
    user_message: str,
    current_state: Optional[Dict[str, Any]] = None,
    *,
    model: Optional[str] = None,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Extract one turn and return the resulting full conversation state."""
    update = extract_preference_update(
        user_message,
        current_state,
        model=model,
        client=client,
    )
    return merge_preference_state(current_state, update)


def to_decision_preferences(state: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt structured targets and priorities to the deterministic scorer.

    A soft budget target remains independent and is never promoted to
    ``max_price``. Semantic priorities remain semantic at this boundary; the
    decision layer owns their deterministic numeric conversion.
    """
    hard = state["hard_constraints"]
    soft = state["soft_preferences"]

    preferences = {
        "requested_size": hard.get("size"),
        "max_price": hard.get("max_price"),
        "exclude_latex": hard.get("exclude_latex") is True,
        "require_CA_haul_away": hard.get("require_CA_haul_away") is True,
        "budget_target": soft.get("budget_target"),
        "budget_flex_max": soft.get("budget_flex_max"),
        "prefer_CA_haul_away": soft.get("prefer_CA_haul_away") is True,
        "directions": deepcopy(state.get("directions", {})),
        "priorities": deepcopy(state.get("priorities", {})),
    }
    target_mapping = {
        "firmness_target": "firmness_preference",
        "support_target": "support_preference",
        "cooling_target": "cooling_preference",
        "motion_isolation_target": "motion_isolation_preference",
    }
    for state_key, decision_key in target_mapping.items():
        if soft.get(state_key) is not None:
            preferences[decision_key] = soft[state_key]
    return preferences
