"""Deterministic trust-boundary assessment for live shopping journeys."""

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from engine.decision import constraint_violations


def actual_turns(actual: Dict[str, Any]) -> List[Dict[str, Any]]:
    turns = []
    for item in actual.get("turns", []):
        turn = deepcopy(item.get("turn", item))
        for key in (
            "user",
            "input_state",
            "parsed_state",
            "decision_result",
            "decision_preferences",
            "shopping_selection",
            "grounding_evidence",
            "presentation_contract",
            "final_shopper_response",
            "generation_audit",
        ):
            if key in item:
                turn[key] = deepcopy(item[key])
        turns.append(turn)
    return turns


def _presentation(turn: Dict[str, Any]) -> Dict[str, Any]:
    return turn.get("presentation_contract") or turn.get("presentation") or {}


def _decision(turn: Dict[str, Any]) -> Dict[str, Any]:
    return turn.get("decision_result") or {}


def _shopper_state(turn: Dict[str, Any]) -> Dict[str, Any]:
    return turn.get("parsed_state") or turn.get("preference_state") or {}


def _final_generation_is_safe(turn: Dict[str, Any]) -> bool:
    audit = turn.get("generation_audit") or {}
    if not audit or audit.get("fallback_used"):
        return True
    attempts = audit.get("attempts") or []
    return bool(attempts and attempts[-1].get("valid"))


def evaluate_system_integrity(
    case: Dict[str, Any],
    actual: Dict[str, Any],
    *,
    invariant_outcomes: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Assess only safety, facts, authority, and consequential state integrity."""
    turns = actual_turns(actual)
    non_negotiable_issues: List[str] = []
    grounding_issues: List[str] = []
    authority_issues: List[str] = []
    state_issues: List[str] = []

    for index, turn in enumerate(turns, start=1):
        decision = _decision(turn)
        selection = turn.get("shopping_selection") or {}
        legacy_selected = decision.get("selected_sku") or {}
        selection_ids = selection.get("selected_product_ids") or (
            [legacy_selected.get("sku_id")] if legacy_selected.get("sku_id") else []
        )
        candidates = {
            item.get("sku_id"): item for item in decision.get("ranked_candidates", [])
        }
        if legacy_selected.get("sku_id"):
            candidates.setdefault(legacy_selected["sku_id"], legacy_selected)
        if decision.get("decision") == "ALLOW":
            validation = selection.get("validation") or {}
            if not selection or not validation.get("valid"):
                authority_issues.append(
                    f"Turn {index} lacks a passing authoritative selection contract."
                )
            missing = [sku_id for sku_id in selection_ids if sku_id not in candidates]
            if missing:
                authority_issues.append(
                    f"Turn {index} selected products outside the eligible candidate set: {', '.join(missing)}."
                )

        for selected_id in selection_ids:
            selected = candidates.get(selected_id)
            if not selected:
                continue
            preferences = turn.get("decision_preferences") or {}
            if not preferences:
                state = _shopper_state(turn)
                preferences = {
                    "requested_size": (state.get("hard_constraints") or {}).get("size"),
                    "max_price": (state.get("hard_constraints") or {}).get("max_price"),
                    "exclude_latex": (state.get("hard_constraints") or {}).get("exclude_latex"),
                    "require_CA_haul_away": (state.get("hard_constraints") or {}).get("require_CA_haul_away"),
                }
            violations = constraint_violations(preferences, selected)
            if violations:
                non_negotiable_issues.append(
                    f"Turn {index} selected {selected.get('sku_id')} despite {', '.join(violations)}."
                )

        products = _presentation(turn).get("products") or []
        presented_ids = [item.get("sku_id") for item in products]
        if selection_ids and presented_ids != selection_ids:
            authority_issues.append(
                f"Turn {index} presentation identities/order do not match the validated selection."
            )
        primary = selection.get("primary_product_id")
        if primary is not None and (not selection_ids or primary != selection_ids[0]):
            authority_issues.append(
                f"Turn {index} primary product is not first in the validated selection."
            )

        if not _final_generation_is_safe(turn):
            grounding_issues.append(
                f"Turn {index} delivered generated language without a passing grounding validation."
            )

        if turn.get("extraction_error"):
            before = turn.get("previous_preference_state") or turn.get("input_state")
            after = turn.get("preference_state") or turn.get("parsed_state")
            if before != after:
                state_issues.append(
                    f"Turn {index} changed the last valid state after extraction failure."
                )

    expected_turns = case.get("turns", [])
    for index, (expected_turn, actual_turn) in enumerate(
        zip(expected_turns, turns), start=1
    ):
        expected_hard = (
            expected_turn.get("expected", {}).get("state", {}).get("hard_constraints", {})
        )
        actual_hard = _shopper_state(actual_turn).get("hard_constraints", {})
        for field, expected_value in expected_hard.items():
            if expected_value is not None and actual_hard.get(field) != expected_value:
                non_negotiable_issues.append(
                    f"Turn {index} did not preserve expected hard requirement {field}={expected_value!r}."
                )

    applicable_invariants = dict(invariant_outcomes or {})
    failed_invariants = [name for name, passed in applicable_invariants.items() if not passed]
    passed = not (
        non_negotiable_issues
        or grounding_issues
        or authority_issues
        or state_issues
        or failed_invariants
    )
    if passed:
        rationale = (
            "No trust-boundary violation was observed in the delivered journey: "
            "non-negotiables, represented evidence, authoritative selection, and consequential state were preserved."
        )
    else:
        rationale = "One or more trust-boundary checks failed; see the findings below."
    return {
        "status": "PASS" if passed else "FAIL",
        "critical_invariants": applicable_invariants,
        "non_negotiable_issues": non_negotiable_issues,
        "grounding_or_factual_issues": grounding_issues,
        "recommendation_authority_issues": authority_issues,
        "state_integrity_issues": state_issues,
        "rationale": rationale,
    }
