"""Contextual customer prose over deterministic turn results."""

import json
import os
import re
from typing import Any, Dict, Iterable, Iterator, Optional

from dotenv import load_dotenv
from openai import OpenAI

from engine.customer_copy import contains_internal_language
from engine.grounding import (
    RECOMMENDATION_TERMS,
    UNSUPPORTED_CAPABILITY_PATTERNS,
    known_product_references,
    validate_recommendation_text,
    validate_review_text,
)
from engine.prompts import load_customer_prompt, load_prompt
from engine.model_config import (
    ModelConfiguration,
    generation_task_for_turn,
    model_configuration,
    public_model_configuration,
    responses_request_options,
)
from engine.timing import complete_turn, mark_timing, new_turn_timing, set_response_path


BASE_INSTRUCTION = load_customer_prompt("conversational_turn.md")
RETRY_INSTRUCTION = f"{BASE_INSTRUCTION}\n\n{load_prompt('grounded_retry.md')}"


def _model_output(
    client: Any,
    config: ModelConfiguration,
    payload: Dict[str, Any],
    instruction: str,
) -> str:
    if hasattr(client, "responses"):
        response = client.responses.create(
            **responses_request_options(config),
            input=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        return response.output_text
    response = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    return response.choices[0].message.content


def _model_output_stream(
    client: Any,
    config: ModelConfiguration,
    payload: Dict[str, Any],
    instruction: str,
) -> Iterator[str]:
    """Yield text deltas from Responses or Chat Completions clients."""
    if hasattr(client, "responses"):
        events = client.responses.create(
            **responses_request_options(config),
            stream=True,
            input=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        for event in events:
            event_type = getattr(event, "type", None)
            delta = getattr(event, "delta", None)
            if isinstance(event, dict):
                event_type = event.get("type")
                delta = event.get("delta")
            if event_type == "response.output_text.delta" and delta:
                yield str(delta)
        return

    chunks = client.chat.completions.create(
        model=config.model,
        stream=True,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    for chunk in chunks:
        choices = getattr(chunk, "choices", [])
        if choices:
            delta = getattr(choices[0].delta, "content", None)
            if delta:
                yield delta


def _validate_general_response(
    text: str,
    turn: Dict[str, Any],
    catalog: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    reasons = []
    if not text or not text.strip():
        reasons.append("empty_response")
    if contains_internal_language(text):
        reasons.append("internal_customer_language")
    for capability, pattern in UNSUPPORTED_CAPABILITY_PATTERNS.items():
        if pattern.search(text):
            reasons.append(f"unsupported_capability:{capability}")

    grounding_text = json.dumps(
        {
            "grounding_data": turn.get("grounding_data"),
            "recovery": turn.get("recovery"),
            "fallback": turn.get("response_text"),
        }
    )
    allowed_money = {
        int(float(value.replace(",", "")))
        for value in re.findall(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", grounding_text)
    }
    grounding = turn.get("grounding_data") or {}
    product_prices = {
        int(product["price"])
        for product in grounding.get("products", [])
        if isinstance(product.get("price"), (int, float))
    }
    grounded_product = grounding.get("product") or {}
    if isinstance(grounded_product.get("price"), (int, float)):
        product_prices.add(int(grounded_product["price"]))
    allowed_money.update(product_prices)
    if len(product_prices) > 1:
        allowed_money.update(
            abs(left - right)
            for left in product_prices
            for right in product_prices
            if left != right
        )
    for raw_value in re.findall(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text):
        if int(float(raw_value.replace(",", ""))) not in allowed_money:
            reasons.append("unrepresented_price")

    if grounding.get("verified") is False and re.search(
        r"\b(?:does not|doesn't|is not available|isn't available|no [a-z-]+)\b",
        text,
        re.IGNORECASE,
    ):
        reasons.append("unknown_presented_as_false")

    allowed_names = set()
    for product in grounding.get("products", []):
        if product.get("name"):
            allowed_names.add(product["name"].casefold())
    if grounded_product.get("name"):
        allowed_names.add(grounded_product["name"].casefold())
    fallback = str(turn.get("response_text") or "").casefold()
    for product in catalog:
        name = str(product.get("name", ""))
        if name and name.casefold() in fallback:
            allowed_names.add(name.casefold())
        if name and name.casefold() in text.casefold() and name.casefold() not in allowed_names:
            reasons.append(f"unrepresented_product:{product.get('sku_id', '')}")

    decision_result = turn.get("decision_result") or {}
    if decision_result.get("decision") == "BLOCK" and RECOMMENDATION_TERMS.search(text):
        reasons.append("blocked_outcome_presented_as_recommendation")
    review = grounding.get("review_evidence") if isinstance(grounding, dict) else None
    if turn.get("response_strategy") == "review_evidence_lookup":
        review = grounding
    if review:
        reasons.extend(validate_review_text(text, review)["reasons"])
    return {"valid": not reasons, "reasons": list(dict.fromkeys(reasons))}


def _response_payload(
    turn: Dict[str, Any],
    latest_user_message: str,
    conversation_history: Optional[Iterable[Dict[str, str]]],
    fallback: str,
) -> Dict[str, Any]:
    return {
        "latest_user_message": latest_user_message,
        "conversation_history": list(conversation_history or [])[-8:],
        "intent": turn.get("intent"),
        "shopping_action": turn.get("shopping_action"),
        "response_strategy": turn.get("response_strategy"),
        "presentation": turn.get("presentation"),
        "shopper_state": turn.get("preference_state"),
        "state_changes": turn.get("state_changes"),
        "grounding_data": turn.get("grounding_data"),
        "grounding_evidence": turn.get("grounding_evidence"),
        "shopping_selection": turn.get("shopping_selection"),
        "recovery": turn.get("recovery"),
        "deterministic_fallback": fallback,
    }


def _validate_response(
    text: str, turn: Dict[str, Any], catalog: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    decision_result = turn.get("decision_result") or {}
    if turn.get("grounding_evidence") and decision_result.get("decision") == "ALLOW":
        presentation = turn.get("presentation") or {}
        structured_product_ids = []
        if presentation.get("modality") == "recommendation_cards":
            structured_product_ids = [
                product.get("sku_id")
                for product in presentation.get("products", [])
                if product.get("sku_id")
            ]
        validation = validate_recommendation_text(
            text,
            turn["grounding_evidence"],
            known_product_references(catalog),
            structured_product_ids=structured_product_ids,
        )
        if contains_internal_language(text):
            validation["valid"] = False
            validation["reasons"].append("internal_customer_language")
        return validation
    return _validate_general_response(text, turn, catalog)


def _record_review_language(turn: Dict[str, Any], text: str) -> None:
    review_debug = turn.get("review_debug")
    if isinstance(review_debug, dict) and re.search(
        r"\b(?:reviewers?|owners?|customers?|review feedback|customer feedback|common theme)\b",
        text,
        re.IGNORECASE,
    ):
        review_debug["appeared_in_explanation"] = True


def _timing_for(turn: Dict[str, Any], timing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    resolved = timing or turn.get("timing")
    if resolved is None:
        resolved = new_turn_timing()
        turn["timing"] = resolved
    return resolved


def generate_turn_response(
    turn: Dict[str, Any],
    latest_user_message: str,
    conversation_history: Optional[Iterable[Dict[str, str]]] = None,
    *,
    catalog: Iterable[Dict[str, Any]] = (),
    model: Optional[str] = None,
    client: Optional[Any] = None,
    audit: Optional[Dict[str, Any]] = None,
    timing: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate contextual prose, retry once, and return the safe turn fallback."""
    fallback = turn.get("response_text")
    if not fallback:
        raise ValueError("turn must include deterministic fallback copy")
    timing = _timing_for(turn, timing)

    task = generation_task_for_turn(turn)
    if task is None:
        if audit is not None:
            audit.update({"generated": False, "fallback_used": True, "reason": "fixed_response"})
        set_response_path(timing, "deterministic_fallback", generation_status="not_started")
        mark_timing(timing, "response_visible_at")
        complete_turn(timing)
        return fallback

    config = model_configuration(task, model_override=model)
    if audit is not None:
        audit["model_route"] = public_model_configuration(config)

    load_dotenv()
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            if audit is not None:
                audit.update({"generated": False, "fallback_used": True, "reason": "model_unavailable"})
            set_response_path(timing, "deterministic_fallback", generation_status="unavailable")
            mark_timing(timing, "response_visible_at")
            complete_turn(timing)
            return fallback
        client = OpenAI(api_key=api_key)

    payload = _response_payload(turn, latest_user_message, conversation_history, fallback)
    catalog_list = list(catalog)
    attempts = []
    mark_timing(timing, "generation_started_at")
    timing["generation_status"] = "running"
    for attempt, instruction in enumerate((BASE_INSTRUCTION, RETRY_INSTRUCTION), start=1):
        try:
            text = _model_output(client, config, payload, instruction)
            mark_timing(timing, "first_token_at")
        except Exception as error:
            attempts.append({"attempt": attempt, "valid": False, "reasons": ["generation_error"], "error": type(error).__name__})
            break

        validation = _validate_response(text, turn, catalog_list)
        attempts.append({"attempt": attempt, **validation})
        if validation["valid"]:
            _record_review_language(turn, text)
            if audit is not None:
                audit.update({"generated": True, "fallback_used": False, "attempts": attempts})
            mark_timing(timing, "generation_completed_at")
            set_response_path(timing, "buffered", generation_status="completed")
            mark_timing(timing, "response_visible_at")
            complete_turn(timing)
            return text.strip()

    if audit is not None:
        audit.update({"generated": False, "fallback_used": True, "attempts": attempts})
    mark_timing(timing, "generation_completed_at")
    set_response_path(timing, "deterministic_fallback", generation_status="failed")
    mark_timing(timing, "response_visible_at")
    complete_turn(timing)
    return fallback


def generate_turn_response_stream(
    turn: Dict[str, Any],
    latest_user_message: str,
    conversation_history: Optional[Iterable[Dict[str, str]]] = None,
    *,
    catalog: Iterable[Dict[str, Any]] = (),
    model: Optional[str] = None,
    client: Optional[Any] = None,
    audit: Optional[Dict[str, Any]] = None,
    timing: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """Safely stream only after a complete response passes grounding validation.

    Model deltas are buffered at the validation boundary. The structured UI can be
    shown while they arrive, but no unvalidated claim is yielded to the shopper.
    """
    fallback = turn.get("response_text")
    if not fallback:
        raise ValueError("turn must include deterministic fallback copy")
    timing = _timing_for(turn, timing)

    task = generation_task_for_turn(turn)
    fixed = task is None
    config = model_configuration(task, model_override=model) if task else None
    if audit is not None and config is not None:
        audit["model_route"] = public_model_configuration(config)
    load_dotenv()
    if client is None and not fixed:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            client = OpenAI(api_key=api_key)

    attempts = []
    approved_text = None
    if not fixed and client is not None:
        payload = _response_payload(
            turn, latest_user_message, conversation_history, fallback
        )
        catalog_list = list(catalog)
        mark_timing(timing, "generation_started_at")
        timing["generation_status"] = "running"
        for attempt, instruction in enumerate(
            (BASE_INSTRUCTION, RETRY_INSTRUCTION), start=1
        ):
            try:
                deltas = []
                for delta in _model_output_stream(client, config, payload, instruction):
                    if delta:
                        mark_timing(timing, "first_token_at")
                        deltas.append(delta)
                text = "".join(deltas).strip()
            except Exception as error:
                attempts.append(
                    {
                        "attempt": attempt,
                        "valid": False,
                        "reasons": ["generation_error"],
                        "error": type(error).__name__,
                    }
                )
                break
            validation = _validate_response(text, turn, catalog_list)
            attempts.append({"attempt": attempt, **validation})
            if validation["valid"]:
                approved_text = text
                _record_review_language(turn, text)
                break
        mark_timing(timing, "generation_completed_at")

    if approved_text is not None:
        set_response_path(timing, "streamed", generation_status="completed")
        if audit is not None:
            audit.update(
                {
                    "generated": True,
                    "fallback_used": False,
                    "delivery": "validation_buffered_stream",
                    "attempts": attempts,
                }
            )
        output = approved_text
    else:
        status = "not_started" if fixed else ("unavailable" if client is None else "failed")
        set_response_path(timing, "deterministic_fallback", generation_status=status)
        if audit is not None:
            audit.update(
                {
                    "generated": False,
                    "fallback_used": True,
                    "reason": "fixed_response" if fixed else status,
                    "attempts": attempts,
                }
            )
        output = fallback

    try:
        for chunk in re.findall(r"\S+\s*", output):
            mark_timing(timing, "response_visible_at")
            yield chunk
    finally:
        complete_turn(timing)
