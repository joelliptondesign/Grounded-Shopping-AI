"""Deterministic clarification and no-match recovery strategies."""

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from engine.decision import filter_eligible_skus


CONSTRAINT_LABELS = {
    "size_constraint": "requested size",
    "max_price": "maximum price",
    "latex_constraint": "latex exclusion",
    "require_CA_haul_away": "haul-away requirement",
    "unknown_size_constraint": "requested-size data",
    "unknown_max_price": "price data",
    "unknown_latex_constraint": "latex data",
    "unknown_require_CA_haul_away": "haul-away availability",
}


def _option(
    option_type: str,
    constraint: str,
    proposed_value: Any,
    match_count: int,
    state_patch: Dict[str, Any],
    *,
    scoped_sku_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    result = {
        "type": option_type,
        "constraint": constraint,
        "proposed_value": proposed_value,
        "match_count": match_count,
        "state_patch": state_patch,
    }
    if scoped_sku_ids:
        result["scoped_sku_ids"] = scoped_sku_ids
    return result


def _preferences_with(preferences: Dict[str, Any], **changes: Any) -> Dict[str, Any]:
    hypothetical = deepcopy(preferences)
    hypothetical.update(changes)
    return hypothetical


def grounded_relaxation_options(
    preferences: Dict[str, Any], catalog: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Return only one-change relaxations that deterministically yield matches."""
    catalog_list = list(catalog)
    options: List[Dict[str, Any]] = []

    current_max = preferences.get("max_price")
    if current_max is not None:
        without_max, _ = filter_eligible_skus(
            _preferences_with(preferences, max_price=None), catalog_list
        )
        known_prices = sorted(
            {
                sku["price"]
                for sku in without_max
                if "price" in sku and sku["price"] > current_max
            }
        )
        if known_prices:
            proposed = known_prices[0]
            matches, _ = filter_eligible_skus(
                _preferences_with(preferences, max_price=proposed), catalog_list
            )
            options.append(
                _option(
                    "relax_max_price",
                    "max_price",
                    proposed,
                    len(matches),
                    {"hard_constraints": {"max_price": proposed}},
                )
            )

    if preferences.get("require_CA_haul_away") is True:
        matches, _ = filter_eligible_skus(
            _preferences_with(preferences, require_CA_haul_away=False), catalog_list
        )
        if matches:
            options.append(
                _option(
                    "remove_haul_away_requirement",
                    "require_CA_haul_away",
                    False,
                    len(matches),
                    {"hard_constraints": {"require_CA_haul_away": False}},
                )
            )

    return options


def _count_active_constraints(preferences: Dict[str, Any]) -> int:
    return sum(
        (
            preferences.get("requested_size") is not None,
            preferences.get("max_price") is not None,
            preferences.get("exclude_latex") is True,
            preferences.get("require_CA_haul_away") is True,
        )
    )


def _proposal_text(option: Dict[str, Any], preferences: Dict[str, Any]) -> str:
    count = option["match_count"]
    noun = "option" if count == 1 else "options"
    if option["type"] == "relax_max_price":
        return (
            f"Your ${preferences['max_price']:,.0f} ceiling is what narrows things "
            f"down the most. If you can stretch to ${option['proposed_value']:,.0f}, "
            f"I have {count} {noun} that still fits the other requirements. "
            "Should I show you that, or keep the current limit?"
        )
    if option["type"] == "remove_haul_away_requirement":
        return f"I found {count} {noun} without haul-away. Want to remove that requirement?"
    return f"I found {count} {noun} if latex is allowed. Want to remove that requirement?"


def build_no_match_recovery(
    preferences: Dict[str, Any],
    catalog: Iterable[Dict[str, Any]],
    decision_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Translate an authoritative block into a concise, grounded recovery."""
    options = grounded_relaxation_options(preferences, catalog)
    unknowns = sorted(
        {
            item
            for excluded in decision_result.get("metadata", {}).get(
                "excluded_candidates", []
            )
            for item in excluded.get("unknowns", [])
        }
    )
    known_blockers = [
        item
        for item in decision_result.get("violations", [])
        if not item.startswith("unknown_")
    ]
    if unknowns and not known_blockers:
        options = []
    count = _count_active_constraints(preferences)
    requirement_phrase = (
        f"all {count} requirements" if count > 1 else "that requirement"
    )
    message = f"I couldn't find a mattress that meets {requirement_phrase}."
    if options:
        message += " " + _proposal_text(options[0], preferences)
    elif unknowns:
        labels = [CONSTRAINT_LABELS[item] for item in unknowns if item in CONSTRAINT_LABELS]
        detail = labels[0] if labels else "required catalog data"
        message = f"I couldn't verify {detail} for an otherwise eligible match."

    return {
        "recovery_type": "no_exact_match" if options else "missing_data" if unknowns else "no_exact_match",
        "message": message,
        "blocking_constraints": decision_result.get("violations", []),
        "unknown_constraints": unknowns,
        "options": options,
        "proposed_relaxation": options[0] if options else None,
        "requires_user_approval": bool(options),
    }


def build_product_conflict_recovery(
    product: Dict[str, Any], violations: List[str], current_max: Optional[float]
) -> Optional[Dict[str, Any]]:
    """Build a resolvable exact-product conflict without changing state."""
    if violations == ["max_price"] and "price" in product:
        option = _option(
            "relax_max_price",
            "max_price",
            product["price"],
            1,
            {"hard_constraints": {"max_price": product["price"]}},
            scoped_sku_ids=[product["sku_id"]],
        )
        return {
            "recovery_type": "conflicting_requirements",
            "message": (
                f"Yep, I can show you {product['name']}. Just a heads-up: it's "
                f"${product['price']:,.0f}, which is above the ${current_max:,.0f} "
                "maximum you set. Are you open to raising the limit for this "
                "comparison, or should I keep your current ceiling?"
            ),
            "blocking_constraints": violations,
            "options": [option],
            "proposed_relaxation": option,
            "requires_user_approval": True,
        }
    return None


def pending_from_recovery(recovery: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    proposal = recovery.get("proposed_relaxation")
    if not recovery.get("requires_user_approval") or not proposal:
        return None
    return {
        "recovery_type": recovery["recovery_type"],
        "proposal": deepcopy(proposal),
    }


def apply_state_patch(state: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(state)
    for section, values in patch.items():
        if isinstance(values, dict):
            updated.setdefault(section, {}).update(deepcopy(values))
        else:
            updated[section] = deepcopy(values)
    return updated
