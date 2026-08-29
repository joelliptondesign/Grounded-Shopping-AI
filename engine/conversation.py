"""Intent router with explicit clarification and deterministic recovery."""

import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Tuple

from engine.decision import constraint_violations, evaluate_decision
from engine.grounding import AUTHORITATIVE_SOURCES, build_recommendation_evidence
from engine.review_data import REVIEW_FIXTURE_SOURCE, review_slice
from engine.preference_extraction import (
    extract_preference_update,
    merge_preference_state,
    new_preference_state,
    to_decision_preferences,
)
from engine.recovery import (
    apply_state_patch,
    build_no_match_recovery,
    build_product_conflict_recovery,
    pending_from_recovery,
)
from engine.response_strategy import (
    build_comparison,
    service_availability,
    add_comparison_reviews,
    build_product_fact,
    build_review_fact,
    build_service_fact,
    find_products,
    render_comparison,
    render_product_fact,
    render_review_fact,
    render_service_fact,
    strategy_for_intent,
)
from engine.customer_copy import (
    COLD_START_FOLLOW_UPS,
    EXTRACTION_RECOVERY,
    off_topic_fallback,
)
from engine.elicitation import (
    build_cold_start_elicitation,
    resolve_elicitation_response,
)
from engine.presentation import build_turn_presentation
from engine.shopping_selection import (
    deterministic_selection_fallback,
    select_shopping_products,
)
from engine.timing import mark_timing, new_turn_timing


EXTRACTION_RECOVERY_MESSAGE = EXTRACTION_RECOVERY


def _state_changes(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    changes: Dict[str, Any] = {}
    for section in ("hard_constraints", "soft_preferences", "directions", "priorities"):
        section_changes = {}
        before_values = before.get(section, {})
        after_values = after.get(section, {})
        for key in set(before_values) | set(after_values):
            if before_values.get(key) != after_values.get(key):
                section_changes[key] = {
                    "before": before_values.get(key),
                    "after": after_values.get(key),
                }
        if section_changes:
            changes[section] = section_changes
    for key in ("recommendation_readiness", "needs_clarification", "clarification_reason"):
        if before.get(key) != after.get(key):
            changes[key] = {"before": before.get(key), "after": after.get(key)}
    return changes


def _base_result(
    intent: str,
    strategy: str,
    previous_state: Dict[str, Any],
    preference_state: Dict[str, Any],
    timing: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "intent": intent,
        "shopping_action": None,
        "response_strategy": strategy,
        "preference_state": preference_state,
        "previous_preference_state": deepcopy(previous_state),
        "updated_preference_state": deepcopy(preference_state),
        "state_changes": _state_changes(previous_state, preference_state),
        "decision_preferences": None,
        "decision_result": None,
        "shopping_selection": None,
        "grounding_data": None,
        "grounding_evidence": None,
        "recovery": None,
        "pending_elicitation": deepcopy(preference_state.get("pending_elicitation")),
        "elicitation_type": (
            (preference_state.get("pending_elicitation") or {}).get("response_type")
        ),
        "elicitation_response": None,
        "structured_option_selected": None,
        "skipped_to_options": False,
        "extraction_error": None,
        "review_debug": {
            "evidence_requested": False,
            "review_topic": None,
            "fixture_source": REVIEW_FIXTURE_SOURCE,
            "themes_used": [],
            "unknown_review_topics": [],
            "evidence_included_in_grounding": False,
            "appeared_in_explanation": False,
            "appeared_in_cards": False,
            "appeared_in_comparison": False,
        },
        "pipeline_actions": {
            "eligibility_recomputed": False,
            "ranking_recomputed": False,
            "shopping_selection_generated": False,
        },
        "response_text": None,
        "modality": None,
        "modality_reason": None,
        "presentation": None,
        "timing": timing,
        "scope_guardrail": {
            "in_scope": intent != "off_topic",
            "result": "allow" if intent != "off_topic" else "blocked",
        },
    }


def _finish(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the deterministic, renderer-independent presentation contract."""
    mark_timing(result["timing"], "decision_ready_at")
    presentation = build_turn_presentation(result)
    result["presentation"] = presentation
    result["modality"] = presentation["modality"]
    result["modality_reason"] = presentation["selection_reason"]
    if presentation["modality"] != "conversation":
        result["response_text"] = presentation["message"]
    displayed_names = [
        product.get("name")
        for product in presentation.get("products", [])
        if product.get("name")
    ]
    comparison = presentation.get("comparison") or {}
    displayed_names.extend(name for name in comparison.get("product_names", []) if name)
    if displayed_names:
        result["preference_state"]["recent_product_names"] = list(
            dict.fromkeys(displayed_names)
        )
        _refresh_state_debug(result)
    presentation_record = _presentation_record(result, presentation)
    if presentation_record:
        recent = list(result["preference_state"].get("recent_presentations", []))
        recent.append(presentation_record)
        result["preference_state"]["recent_presentations"] = recent[-4:]
        _refresh_state_debug(result)
    mark_timing(result["timing"], "presentation_ready_at")
    return result


def _refresh_state_debug(result: Dict[str, Any]) -> None:
    state = result["preference_state"]
    result["updated_preference_state"] = deepcopy(state)
    result["state_changes"] = _state_changes(
        result["previous_preference_state"], state
    )


def _extraction_failure(
    current_state: Optional[Dict[str, Any]], error: Exception, timing: Dict[str, Any]
) -> Dict[str, Any]:
    preserved = deepcopy(current_state) if current_state is not None else new_preference_state()
    result = _base_result(
        "recommend", "extraction_recovery", preserved, preserved, timing
    )
    result["recovery"] = {
        "recovery_type": "extraction_failure",
        "message": EXTRACTION_RECOVERY_MESSAGE,
        "blocking_constraints": [],
        "options": [],
        "requires_user_approval": False,
    }
    result["grounding_data"] = result["recovery"]
    result["response_text"] = EXTRACTION_RECOVERY_MESSAGE
    result["extraction_error"] = {
        "type": type(error).__name__,
        "message": str(error),
    }
    return _finish(result)


def _has_explicit_hard_update(update: Dict[str, Any]) -> bool:
    return any(value is not None for value in update.get("hard_constraints", {}).values())


def _apply_state_patch(state: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for section in ("hard_constraints", "soft_preferences", "directions", "priorities"):
        for key, value in patch.get(section, {}).items():
            state.setdefault(section, {})[key] = value


def _structured_resume_update(
    previous_state: Dict[str, Any], response: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    resolved = resolve_elicitation_response(
        previous_state.get("pending_elicitation"), response
    )
    resumed = deepcopy(previous_state)
    _apply_state_patch(resumed, resolved["state_patch"])
    resumed["pending_elicitation"] = None
    resumed["needs_clarification"] = False
    resumed["clarification_question"] = None
    resumed["clarification_reason"] = None
    hard = resumed.get("hard_constraints", {})
    soft = resumed.get("soft_preferences", {})
    has_basic = hard.get("size") is not None or soft.get("budget_target") is not None
    resumed["recommendation_readiness"] = "exploratory" if has_basic else "low"
    update = {
        "intent": "recommend",
        "shopping_action": {
            "action": "recommend_products",
            "product_ids": [],
            "product_attribute": None,
            "service_attribute": None,
        },
        "turn_context": {
            "product_names": [],
            "product_attribute": None,
            "service_attribute": None,
            "exact_product_request": False,
            "information_source": None,
            "review_topic": None,
            "explicit_browse_intent": resolved["skipped_to_options"],
        },
        "recovery_response": "none",
        "hard_constraints": deepcopy(resumed["hard_constraints"]),
        "soft_preferences": deepcopy(resumed["soft_preferences"]),
        "directions": deepcopy(resumed["directions"]),
        "priorities": deepcopy(resumed["priorities"]),
        "needs_clarification": False,
        "clarification_question": None,
        "clarification_reason": None,
        "recommendation_readiness": resumed["recommendation_readiness"],
    }
    return update, resolved


# Size and approximate budget markedly improve a first shortlist, so the agent
# gets two lightweight attempts to collect them — never more, and never as a gate.
MAX_COLD_START_QUESTIONS = 2

_DECLINES_BASICS = re.compile(
    r"\b(just show|show me (some|any|options|what)|browse|"
    r"i (don'?t|do not) know|dunno|no idea|not sure|unsure|"
    r"(doesn'?t|does not) matter|no (real )?budget|"
    r"whatever|any(thing)? (is )?fine|no preference|not important|skip)\b",
    re.IGNORECASE,
)


def _declines_basics(user_message: str) -> bool:
    """Detect a shopper waving the cold-start basics off, so we stop asking."""
    return bool(_DECLINES_BASICS.search(user_message or ""))


# A haul-away question about a shortlist is a service need, not only a fact
# request: if nothing on screen carries the service, the shopper still needs a
# mattress that does.
_SERVICE_DISCOVERY = re.compile(
    r"haul[\s-]?away|haul it|get rid of|dispose|disposal|take(s)? (it |them |my |the )?away|removal|remove .{0,20}old|old mattress",
    re.IGNORECASE,
)


def _names_a_product(message: str, catalog: Iterable[Dict[str, Any]]) -> bool:
    """Whether the shopper named a specific product rather than referring to a set.

    "Does CoreFlex Entry include haul-away" stays a narrow fact about that
    product. "Does either include haul-away" is about the shortlist.
    """
    lowered = (message or "").casefold()
    for product in catalog:
        name = str(product.get("name") or "").casefold()
        if not name:
            continue
        if name in lowered:
            return True
        head = " ".join(name.split()[:2])
        if len(head) > 6 and head in lowered:
            return True
    return False


def _service_discovery_alternatives(
    preference_state: Dict[str, Any],
    decision_preferences: Dict[str, Any],
    catalog: List[Dict[str, Any]],
    exclude: Iterable[str],
) -> Dict[str, Any]:
    """Rank catalog options that do carry the service, keeping everything else.

    The shopper's size, budget, priorities and hard constraints are untouched;
    the service requirement is applied for this search only, so it never becomes
    a permanent constraint they did not ask for.
    """
    scoped = deepcopy(decision_preferences)
    scoped["require_CA_haul_away"] = True
    shown = set(exclude)
    candidates = [sku for sku in catalog if sku.get("sku_id") not in shown]
    return evaluate_decision(scoped, candidates)


def _missing_basic(state: Dict[str, Any]) -> Optional[str]:
    """Which of the two high-value basics the shopper still hasn't given."""
    hard = state.get("hard_constraints", {})
    soft = state.get("soft_preferences", {})
    if hard.get("size") is None:
        return "size"
    if hard.get("max_price") is None and soft.get("budget_target") is None:
        return "budget"
    return None


def _apply_cold_start_policy(
    previous_state: Dict[str, Any],
    state: Dict[str, Any],
    update: Dict[str, Any],
    context: Dict[str, Any],
    *,
    intent: str,
    user_message: str = "",
) -> Dict[str, Any]:
    """Try for size and approximate budget, but never block shopping on them."""
    details = {
        "recommendation_readiness": state.get("recommendation_readiness", "low"),
        "clarification_reason": state.get("clarification_reason"),
        "explicit_browse_intent": bool(context.get("explicit_browse_intent")),
        "clarification_bypassed": False,
        "cold_start_questions_asked": int(
            previous_state.get("cold_start_questions_asked") or 0
        ),
    }
    if intent != "recommend":
        return details

    cold_start_clarification = (
        state.get("needs_clarification") is True
        and state.get("clarification_reason") == "cold_start_basics"
    )
    asked = details["cold_start_questions_asked"]
    declined = _declines_basics(user_message)

    if not cold_start_clarification:
        # The shopper answered half of the combined question. Size and budget
        # both markedly improve a first shortlist, so ask once for the other
        # half before recommending — unless they've waved it off or are browsing.
        missing = _missing_basic(state)
        if (
            missing
            and asked
            and asked < MAX_COLD_START_QUESTIONS
            and not declined
            and not details["explicit_browse_intent"]
            and not state.get("needs_clarification")
        ):
            state["needs_clarification"] = True
            state["clarification_reason"] = "cold_start_basics"
            state["clarification_question"] = COLD_START_FOLLOW_UPS[missing]
            state["cold_start_questions_asked"] = asked + 1
            details["clarification_reason"] = "cold_start_basics"
            details["cold_start_questions_asked"] = asked + 1
        return details

    if (
        details["explicit_browse_intent"]
        or declined
        or asked >= MAX_COLD_START_QUESTIONS
    ):
        state["needs_clarification"] = False
        state["clarification_question"] = None
        state["clarification_reason"] = None
        details["clarification_reason"] = "cold_start_basics"
        details["clarification_bypassed"] = True
        return details

    state["cold_start_questions_asked"] = asked + 1
    details["cold_start_questions_asked"] = asked + 1
    return details


def _respect_readiness_certainty(
    selection: Optional[Dict[str, Any]], readiness: str, action_type: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Keep weak-signal multi-product results exploratory without reranking them."""
    if not selection or readiness == "strong" or action_type == "choose_from_products":
        return selection
    if len(selection.get("selected_product_ids", [])) <= 1:
        return selection
    selection["selection_mode"] = "exploratory_shortlist"
    selection["primary_product_id"] = None
    return selection


def _specific_intent(intent: str, context: Dict[str, Any]) -> str:
    """Let a populated, product-scoped topic beat a generic intent label."""
    has_product = bool(context.get("product_names"))
    if has_product and context.get("service_attribute") not in (None, ""):
        return "service_question"
    if has_product and context.get("product_attribute") not in (None, ""):
        return "product_question"
    return intent


def _presentation_record(
    result: Dict[str, Any], presentation: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Capture only the small authoritative slice of UI a shopper could reference."""
    products = presentation.get("products", [])
    product_ids = [item.get("sku_id") for item in products if item.get("sku_id")]
    product_names = [item.get("name") for item in products if item.get("name")]
    grounding = result.get("grounding_data") or {}
    grounded_product = grounding.get("product") if isinstance(grounding, dict) else None
    if not product_ids and isinstance(grounded_product, dict) and grounded_product.get("sku_id"):
        product_ids = [grounded_product["sku_id"]]
        product_names = [grounded_product.get("name")]
    if not product_ids and isinstance(grounding, dict):
        review_ids = [
            item.get("sku_id")
            for item in grounding.get("records", [])
            if item.get("sku_id")
        ]
        if review_ids:
            product_ids = review_ids
            names = grounding.get("product_names", {})
            product_names = [names.get(product_id) for product_id in review_ids]
    product_names = [name for name in product_names if name]
    if not product_ids and presentation.get("modality") == "conversation":
        return None
    action = result.get("shopping_action") or {}
    return {
        "modality": presentation.get("modality"),
        "product_ids": list(dict.fromkeys(product_ids)),
        "product_names": list(dict.fromkeys(product_names)),
        "action": action.get("action"),
        "product_attribute": action.get("product_attribute"),
        "service_attribute": action.get("service_attribute"),
        "information_source": (result.get("turn_context") or {}).get("information_source"),
        "review_topic": (result.get("turn_context") or {}).get("review_topic"),
    }


def _resolved_action(
    update: Dict[str, Any], catalog: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], List[str]]:
    """Resolve model-supplied identity through the catalog and validate action shape."""
    raw = deepcopy(update.get("shopping_action") or {})
    action_type = raw.get("action")
    identifiers = list(raw.get("product_ids") or [])
    if not identifiers:
        identifiers = list((update.get("turn_context") or {}).get("product_names") or [])
    products = find_products(identifiers, catalog)
    ids = [product["sku_id"] for product in products]
    reasons: List[str] = []
    if len(ids) != len(list(dict.fromkeys(identifiers))):
        reasons.append("unknown_product_identity")
    required_counts = {
        "compare_products": 2,
        "choose_from_products": 2,
        "answer_product_question": 1,
    }
    required = required_counts.get(action_type, 0)
    if len(ids) < required:
        reasons.append("insufficient_product_scope")
    normalized = {
        "action": action_type,
        "product_ids": ids,
        "product_attribute": raw.get("product_attribute"),
        "service_attribute": raw.get("service_attribute"),
    }
    return normalized, list(dict.fromkeys(reasons))


def _latest_reference_scope(
    presentations: Iterable[Dict[str, Any]], action_type: Optional[str]
) -> List[str]:
    records = list(presentations)
    preferred = (
        ("comparison_table", "recommendation_cards")
        if action_type in {"compare_products", "choose_from_products"}
        else ("product_detail", "conversation", "comparison_table", "recommendation_cards")
    )
    for modality in preferred:
        for record in reversed(records):
            if record.get("modality") == modality and record.get("product_ids"):
                return list(record["product_ids"])
    return []


def _validate_action_scope(
    action: Dict[str, Any], presentations: Iterable[Dict[str, Any]]
) -> List[str]:
    action_type = action.get("action")
    if action_type not in {"compare_products", "choose_from_products"}:
        return []
    authoritative = _latest_reference_scope(presentations, action_type)
    if not authoritative:
        return []
    ids = action.get("product_ids") or []
    if any(product_id not in authoritative for product_id in ids):
        return ["product_outside_recent_presentation"]
    return []


def _ground_obvious_action(
    action: Dict[str, Any], presentations: Iterable[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Recover identity from authoritative UI after model/action validation failure."""
    action_type = action.get("action")
    scope = _latest_reference_scope(presentations, action_type)
    minimum = 2 if action_type in {"compare_products", "choose_from_products"} else 1
    if len(scope) < minimum:
        return None
    grounded = deepcopy(action)
    grounded["product_ids"] = scope[:2] if minimum == 2 else scope[:1]
    return grounded


def _intent_for_action(action: Dict[str, Any], fallback: str) -> str:
    return {
        "recommend_products": "recommend",
        "compare_products": "compare",
        "choose_from_products": "recommend",
        "answer_product_question": "product_question",
        "answer_service_question": "service_question",
        "off_topic": "off_topic",
    }.get(action.get("action"), fallback)


def process_conversation_turn(
    user_message: str,
    current_state: Optional[Dict[str, Any]],
    catalog: Iterable[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    client: Optional[Any] = None,
    previous_decision_result: Optional[Dict[str, Any]] = None,
    timing: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[Iterable[Dict[str, str]]] = None,
    elicitation_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract one turn, preserve valid state, and route or recover explicitly."""
    timing = timing or new_turn_timing()
    catalog_list = list(catalog)
    previous_state = deepcopy(current_state) if current_state is not None else new_preference_state()
    recent_presentations = list(previous_state.get("recent_presentations", []))[-4:]
    recent_results = {
        "displayed_product_names": previous_state.get("recent_product_names", []),
        "recent_presentations": recent_presentations,
        "catalog_product_identities": [
            {"sku_id": item.get("sku_id"), "name": item.get("name")}
            for item in catalog_list
        ],
        "previous_decision_result": previous_decision_result,
    }
    structured_response = None
    mark_timing(timing, "extraction_started_at")
    try:
        if elicitation_response is not None:
            update, structured_response = _structured_resume_update(
                previous_state, elicitation_response
            )
        else:
            update = extract_preference_update(
                user_message,
                previous_state,
                model=model,
                client=client,
                conversation_history=conversation_history,
                recent_results=recent_results,
            )
    except Exception as error:
        mark_timing(timing, "extraction_completed_at")
        return _extraction_failure(previous_state, error, timing)

    mark_timing(timing, "extraction_completed_at")

    action, action_errors = _resolved_action(update, catalog_list)
    action_errors.extend(_validate_action_scope(action, recent_presentations))
    if action_errors and recent_presentations:
        retry_results = deepcopy(recent_results)
        retry_results["action_validation_retry"] = {
            "invalid_reasons": action_errors,
            "instruction": "Use only the authoritative product IDs in recent_presentations.",
        }
        try:
            retry_update = extract_preference_update(
                user_message,
                previous_state,
                model=model,
                client=client,
                conversation_history=conversation_history,
                recent_results=retry_results,
            )
            retry_action, retry_errors = _resolved_action(retry_update, catalog_list)
            retry_errors.extend(
                _validate_action_scope(retry_action, recent_presentations)
            )
            if not retry_errors:
                update, action, action_errors = retry_update, retry_action, []
        except Exception:
            pass
    if action_errors:
        grounded = _ground_obvious_action(action, recent_presentations)
        if grounded is not None:
            action, action_errors = grounded, []

    preference_state = merge_preference_state(previous_state, update)
    if previous_state.get("pending_elicitation") is not None:
        preference_state["pending_elicitation"] = None
    context = update.get("turn_context") or {}
    intent = _intent_for_action(action, update.get("intent") or "recommend")
    if action.get("action") not in {"compare_products", "choose_from_products"}:
        intent = _specific_intent(intent, context)
    product_names = action.get("product_ids") or context.get("product_names") or []
    result = _base_result(
        intent, strategy_for_intent(intent), previous_state, preference_state, timing
    )
    result["shopping_action"] = action
    result["shopping_action_validation"] = {
        "valid": not action_errors,
        "reasons": action_errors,
    }
    result["turn_context"] = deepcopy(context)
    result["elicitation_response"] = deepcopy(structured_response)
    result["structured_option_selected"] = (
        deepcopy(structured_response.get("selected_option"))
        if structured_response
        else None
    )
    result["skipped_to_options"] = bool(
        structured_response and structured_response.get("skipped_to_options")
    )
    result["cold_start"] = _apply_cold_start_policy(
        previous_state,
        preference_state,
        update,
        context,
        intent=intent,
        user_message=user_message,
    )
    result["recommendation_readiness"] = result["cold_start"][
        "recommendation_readiness"
    ]
    result["clarification_reason"] = result["cold_start"]["clarification_reason"]
    result["explicit_browse_intent"] = result["cold_start"][
        "explicit_browse_intent"
    ]
    result["clarification_bypassed"] = result["cold_start"][
        "clarification_bypassed"
    ]
    _refresh_state_debug(result)

    pending = previous_state.get("pending_recovery")
    recovery_response = update.get("recovery_response", "none")
    scoped_sku_ids = (
        list(action.get("product_ids") or [])
        if action.get("action") == "choose_from_products"
        else None
    )
    if pending and recovery_response == "approve":
        proposal = pending["proposal"]
        preference_state = apply_state_patch(
            preference_state, proposal.get("state_patch", {})
        )
        preference_state["pending_recovery"] = None
        scoped_sku_ids = proposal.get("scoped_sku_ids")
        result["preference_state"] = preference_state
        result["recovery"] = {
            "recovery_type": "approved_relaxation",
            "applied_relaxation": deepcopy(proposal),
            "requires_user_approval": False,
        }
        intent = "recommend"
        result["intent"] = intent
        result["response_strategy"] = strategy_for_intent(intent)
        _refresh_state_debug(result)
    elif pending and recovery_response == "reject":
        preference_state["pending_recovery"] = None
        result["preference_state"] = preference_state
        result["response_strategy"] = "recovery_rejected"
        result["recovery"] = {
            "recovery_type": "relaxation_rejected",
            "message": "Okay—I'll keep your original requirements.",
            "requires_user_approval": False,
        }
        result["grounding_data"] = result["recovery"]
        result["response_text"] = result["recovery"]["message"]
        _refresh_state_debug(result)
        return _finish(result)
    elif pending and intent == "recommend" and _has_explicit_hard_update(update):
        preference_state["pending_recovery"] = None
        result["preference_state"] = preference_state
        _refresh_state_debug(result)

    if intent == "off_topic":
        result["grounding_data"] = {
            "scope": "mattress_shopping",
            "authoritative_source": "validated_turn_intent",
        }
        result["response_text"] = off_topic_fallback(
            user_message,
            has_shopping_context=bool(recent_presentations)
        )
        return _finish(result)

    if preference_state["needs_clarification"]:
        pending_elicitation = None
        if preference_state.get("clarification_reason") == "cold_start_basics":
            pending_elicitation = build_cold_start_elicitation(
                preference_state,
                catalog_list,
                preference_state.get("clarification_question"),
            )
            preference_state["pending_elicitation"] = deepcopy(pending_elicitation)
            result["preference_state"] = preference_state
            result["pending_elicitation"] = deepcopy(pending_elicitation)
            result["elicitation_type"] = (
                pending_elicitation.get("response_type")
                if pending_elicitation
                else None
            )
            _refresh_state_debug(result)
        recovery = {
            "recovery_type": "clarification",
            "message": preference_state["clarification_question"],
            "blocking_constraints": [],
            "options": [],
            "requires_user_approval": False,
        }
        result["response_strategy"] = "clarification"
        result["recovery"] = recovery
        result["grounding_data"] = recovery
        result["response_text"] = recovery["message"]
        return _finish(result)

    if intent == "compare":
        result["grounding_data"] = build_comparison(product_names, catalog_list)
        if context.get("information_source") == "reviews":
            add_comparison_reviews(result["grounding_data"], context.get("review_topic"))
            review = result["grounding_data"]["review_evidence"]
            result["response_strategy"] = "review_comparison"
            result["response_text"] = render_review_fact(review)
            result["review_debug"].update(
                _review_debug(review, requested=True, comparison=True)
            )
        else:
            result["response_text"] = render_comparison(result["grounding_data"])
        return _finish(result)

    if intent == "product_question":
        if context.get("information_source") == "reviews":
            result["grounding_data"] = build_review_fact(
                product_names,
                context.get("review_topic"),
                catalog_list,
                fallback_product=(previous_decision_result or {}).get("selected_sku"),
            )
            result["response_strategy"] = "review_evidence_lookup"
            result["response_text"] = render_review_fact(result["grounding_data"])
            result["review_debug"].update(
                _review_debug(
                    result["grounding_data"], requested=True, explanation=True
                )
            )
        else:
            result["grounding_data"] = build_product_fact(
                product_names, context.get("product_attribute"), catalog_list
            )
            result["response_text"] = render_product_fact(result["grounding_data"])
        return _finish(result)

    if intent == "service_question":
        # A haul-away question naming one product stays a narrow fact. Asked of a
        # shortlist, it is also a service need: answer for everything on screen,
        # and if none of it carries the service, go and find options that do.
        shortlist_question = bool(
            _SERVICE_DISCOVERY.search(user_message)
            and not _names_a_product(user_message, catalog_list)
        )
        scoped_names = product_names or list(
            preference_state.get("recent_product_names", [])
        )[:3]
        availability = (
            service_availability(scoped_names, catalog_list)
            if shortlist_question and scoped_names
            else None
        )

        if availability and availability["products"]:
            result["service_availability"] = availability
            result["grounding_data"] = availability
            result["response_text"] = render_service_fact(availability)
            if not availability["any_available"]:
                return _finish(
                    _service_discovery_turn(
                        result, preference_state, catalog_list, availability
                    )
                )
            return _finish(result)

        previous_product = None
        if previous_decision_result:
            previous_product = previous_decision_result.get("selected_sku")
        result["grounding_data"] = build_service_fact(
            product_names,
            catalog_list,
            service_attribute=context.get("service_attribute"),
            fallback_product=previous_product,
        )
        result["response_text"] = render_service_fact(result["grounding_data"])
        return _finish(result)

    decision_preferences = to_decision_preferences(preference_state)
    decision_catalog = catalog_list
    if scoped_sku_ids:
        decision_catalog = [
            sku for sku in catalog_list if sku.get("sku_id") in scoped_sku_ids
        ]
    elif intent == "recommend" and len(product_names) >= 2:
        compared_products = find_products(product_names, catalog_list)
        if len(compared_products) >= 2:
            decision_catalog = compared_products
    elif context.get("exact_product_request"):
        products = find_products(product_names, catalog_list)
        if products:
            product = products[0]
            violations = constraint_violations(decision_preferences, product)
            conflict = build_product_conflict_recovery(
                product,
                violations,
                decision_preferences.get("max_price"),
            )
            if conflict:
                preference_state["pending_recovery"] = pending_from_recovery(conflict)
                result["preference_state"] = preference_state
                result["response_strategy"] = "conflict_recovery"
                result["recovery"] = conflict
                result["grounding_data"] = conflict
                result["response_text"] = conflict["message"]
                _refresh_state_debug(result)
                return _finish(result)
            decision_catalog = products[:1]

    result["decision_preferences"] = decision_preferences
    result["decision_result"] = evaluate_decision(
        decision_preferences,
        decision_catalog,
        previous_decision_result=previous_decision_result,
    )
    result["pipeline_actions"] = {
        "eligibility_recomputed": bool(
            result["state_changes"].get("hard_constraints")
            or previous_decision_result is None
            or scoped_sku_ids
            or context.get("exact_product_request")
        ),
        "ranking_recomputed": True,
        "shopping_selection_generated": False,
    }
    selection_review = None
    review_topic = _recommendation_review_topic(preference_state)
    if result["decision_result"]["decision"] == "ALLOW" and review_topic:
        candidate_ids = [
            item["sku_id"] for item in result["decision_result"]["ranked_candidates"]
        ]
        selection_review = review_slice(candidate_ids, review_topic)
    if result["decision_result"]["decision"] == "ALLOW":
        result["shopping_selection"] = select_shopping_products(
            result["decision_result"],
            preference_state,
            decision_preferences,
            user_message,
            conversation_history=conversation_history,
            recent_product_names=list(
                dict.fromkeys(
                    list(preference_state.get("recent_product_names", [])) + product_names
                )
            ),
            review_evidence=selection_review,
            model=model,
            client=client,
        )
        result["shopping_selection"] = _respect_readiness_certainty(
            result["shopping_selection"],
            result["recommendation_readiness"],
            action.get("action"),
        )
        result["pipeline_actions"]["shopping_selection_generated"] = not result[
            "shopping_selection"
        ].get("fallback_used", False)
    result["grounding_data"] = result["decision_result"]
    result["grounding_evidence"] = build_recommendation_evidence(
        result["decision_result"],
        decision_preferences,
        shopping_selection=result.get("shopping_selection"),
        approved_relaxation=(result.get("recovery") or {}).get("applied_relaxation"),
    )

    if result["decision_result"]["decision"] == "ALLOW":
        if review_topic:
            selected_ids = result["shopping_selection"]["selected_product_ids"]
            review = review_slice(selected_ids, review_topic)
            by_id = {
                item["sku_id"]: item
                for item in result["decision_result"]["ranked_candidates"]
            }
            review["catalog_context"] = [
                deepcopy(by_id[sku_id]) for sku_id in selected_ids if sku_id in by_id
            ]
            result["grounding_evidence"]["review_evidence"] = review
            result["grounding_evidence"]["review_evidence_is_ranking_input"] = False
            result["review_debug"].update(_review_debug(review))

    if result["decision_result"]["decision"] == "BLOCK":
        recovery = build_no_match_recovery(
            decision_preferences, decision_catalog, result["decision_result"]
        )
        preference_state["pending_recovery"] = pending_from_recovery(recovery)
        result["preference_state"] = preference_state
        result["response_strategy"] = "no_match_recovery"
        result["recovery"] = recovery
        result["grounding_data"] = {
            "decision_result": result["decision_result"],
            "recovery": recovery,
            "authoritative_source": AUTHORITATIVE_SOURCES["recommendation"],
        }
        result["response_text"] = recovery["message"]
        _refresh_state_debug(result)
    return _finish(result)


def _service_discovery_turn(
    result: Dict[str, Any],
    preference_state: Dict[str, Any],
    catalog: List[Dict[str, Any]],
    availability: Dict[str, Any],
) -> Dict[str, Any]:
    """Nothing on screen carries the service — find options that do.

    This is an ordinary recommendation over the same shopper state with the
    service requirement applied, so eligibility, ranking and grounding are the
    engine's usual ones. Selection is the deterministic path: the alternatives
    are already ranked, and the shopper is waiting on a service answer.
    """
    decision_preferences = to_decision_preferences(preference_state)
    shown = [item["sku_id"] for item in availability["products"] if item.get("sku_id")]
    decision = _service_discovery_alternatives(
        preference_state, decision_preferences, catalog, shown
    )
    result["service_discovery"] = {
        "service": availability["service"],
        "region": availability.get("region"),
        "unavailable_for": [item["name"] for item in availability["products"] if item.get("name")],
        "alternatives_found": decision.get("decision") == "ALLOW",
    }
    result["response_strategy"] = "service_discovery"
    if decision.get("decision") != "ALLOW" or not decision.get("ranked_candidates"):
        # Searched and found nothing that keeps the shopper's requirements, so
        # say both halves rather than leaving the answer at "no".
        result["response_text"] = (
            result["response_text"]
            + " I looked for another option that does include it, and nothing"
            " else matches what you're looking for."
        )
        return result

    result["intent"] = "recommend"
    result["decision_preferences"] = decision_preferences
    result["decision_result"] = decision
    result["shopping_selection"] = deterministic_selection_fallback(decision, preference_state)
    result["shopping_selection"]["selected_product_ids"] = result["shopping_selection"][
        "selected_product_ids"
    ][:2]
    result["shopping_selection"]["selections"] = result["shopping_selection"]["selections"][:2]
    result["grounding_evidence"] = build_recommendation_evidence(
        decision, decision_preferences, shopping_selection=result["shopping_selection"]
    )
    result["pipeline_actions"] = {
        "eligibility_recomputed": True,
        "ranking_recomputed": True,
        "shopping_selection_generated": False,
    }
    return result


def process_recommendation_turn(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Backward-compatible entry point now routed by the turn's intent."""
    return process_conversation_turn(*args, **kwargs)


def _recommendation_review_topic(state: Dict[str, Any]) -> Optional[str]:
    """Choose at most one relevant review topic without affecting ranking."""
    supported = {"cooling", "motion_isolation", "firmness"}
    priorities = state.get("priorities", {})
    candidates = [
        (priority, topic)
        for topic, priority in priorities.items()
        if topic in supported and priority in {"high", "critical"}
    ]
    if not candidates:
        return None
    order = {"critical": 2, "high": 1}
    return sorted(candidates, key=lambda item: (-order[item[0]], item[1]))[0][1]


def _review_debug(
    evidence: Dict[str, Any],
    *,
    requested: bool = False,
    explanation: bool = False,
    comparison: bool = False,
) -> Dict[str, Any]:
    themes = sorted(
        {
            topic
            for record in evidence.get("records", [])
            for topic in record.get("themes", {})
        }
    )
    return {
        "evidence_requested": requested,
        "review_topic": evidence.get("requested_topic"),
        "fixture_source": evidence.get("authoritative_source"),
        "themes_used": themes,
        "unknown_review_topics": evidence.get("unknown_topics", []),
        "evidence_included_in_grounding": bool(evidence.get("records")),
        "appeared_in_explanation": explanation,
        "appeared_in_comparison": comparison,
    }
