"""Small, renderer-independent contracts for optional preference elicitation."""

from copy import deepcopy
from typing import Any, Dict, Iterable, Optional


SIZE_LABELS = {
    "twin": "Twin",
    "twin_xl": "Twin XL",
    "full": "Full",
    "queen": "Queen",
    "king": "King",
    "cal_king": "Cal King",
}

BUDGET_OPTIONS = (
    ("under_1000", "Under $1,000", 900, 1000),
    ("1000_1250", "$1,000–$1,250", 1125, 1250),
    ("1250_1500", "$1,250–$1,500", 1375, 1500),
    ("1500_plus", "$1,500+", 1500, None),
)


def _option(option_id: str, label: str, state_patch: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": option_id,
        "label": label,
        "structured_value": {"state_patch": state_patch},
    }


def _supported_sizes(catalog: Iterable[Dict[str, Any]]) -> list[str]:
    represented = {
        size
        for product in catalog
        for size in product.get("available_sizes", [])
    }
    return [size for size in SIZE_LABELS if size in represented]


def build_cold_start_elicitation(
    state: Dict[str, Any],
    catalog: Iterable[Dict[str, Any]],
    question: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build one high-value optional question, never a multi-step form."""
    hard = state.get("hard_constraints", {})
    soft = state.get("soft_preferences", {})
    if hard.get("size") is None:
        options = [
            _option(
                size,
                SIZE_LABELS[size],
                {"hard_constraints": {"size": size}},
            )
            for size in _supported_sizes(catalog)
        ]
        elicitation_id = "mattress_size_v1"
        default_question = "What size mattress are you shopping for?"
    elif soft.get("budget_target") is None and hard.get("max_price") is None:
        options = [
            _option(
                option_id,
                label,
                {
                    "soft_preferences": {
                        "budget_target": target,
                        "budget_flex_max": flex_max,
                    }
                },
            )
            for option_id, label, target, flex_max in BUDGET_OPTIONS
        ]
        elicitation_id = "mattress_budget_range_v1"
        default_question = "Roughly what would you like to spend?"
    else:
        return None

    return {
        "id": elicitation_id,
        "question": question or default_question,
        "response_type": "single_select",
        "options": options,
        "allow_free_text": True,
        "allow_skip": True,
        "skip_label": "Show me options",
        "optional": True,
    }


def resolve_elicitation_response(
    pending: Optional[Dict[str, Any]], response: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve a structured response without asking a model to reinterpret it."""
    if not pending:
        raise ValueError("No structured elicitation is pending")
    if response.get("elicitation_id") != pending.get("id"):
        raise ValueError("Structured elicitation response does not match the pending request")

    action = response.get("action", "select")
    if action == "skip":
        if not pending.get("allow_skip"):
            raise ValueError("This elicitation cannot be skipped")
        return {
            "state_patch": {},
            "selected_option": None,
            "skipped_to_options": True,
        }
    if action != "select":
        raise ValueError("Unsupported structured elicitation action")

    option_id = response.get("option_id")
    option = next(
        (item for item in pending.get("options", []) if item.get("id") == option_id),
        None,
    )
    if option is None:
        raise ValueError("Structured elicitation option is not valid for the pending request")
    return {
        "state_patch": deepcopy(option["structured_value"]["state_patch"]),
        "selected_option": {"id": option["id"], "label": option["label"]},
        "skipped_to_options": False,
    }
