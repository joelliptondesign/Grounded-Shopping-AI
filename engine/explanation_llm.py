"""Grounded recommendation explanations with deterministic failure behavior."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from dotenv import load_dotenv
from openai import OpenAI

from engine.grounding import (
    build_recommendation_evidence,
    known_product_references,
    validate_recommendation_text,
)
from engine.prompts import load_customer_prompt, load_prompt
from engine.customer_copy import contains_internal_language
from engine.model_config import (
    ModelConfiguration,
    ModelTask,
    model_configuration,
    responses_request_options,
)


LOG_FILE = "logs/debug.log"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(event_name: str) -> None:
    line = f"{utc_timestamp()} | {event_name}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as file_handle:
            file_handle.write(line + "\n")
    except OSError:
        # Debug logging must never change the customer-facing fallback path.
        pass


def build_rank_change_explanation(decision_result: Dict[str, Any]) -> Optional[str]:
    """Describe rank movement using only authoritative decision metadata."""
    selected_sku = decision_result.get("selected_sku") or {}
    metadata = decision_result.get("metadata", {})
    previous_sku_id = metadata.get("previous_selected_sku_id")
    selected_sku_id = selected_sku.get("sku_id")
    if not previous_sku_id or previous_sku_id == selected_sku_id:
        return None

    current_weights = metadata.get("active_normalized_weights") or {}
    previous_weights = metadata.get("previous_active_normalized_weights") or {}
    increases = {
        dimension: current_weights.get(dimension, 0) - previous_weights.get(dimension, 0)
        for dimension in current_weights
    }
    increased_dimension = max(increases, key=increases.get) if increases else None
    if increased_dimension is None or increases[increased_dimension] <= 0:
        return None

    previous_sku = next(
        (
            candidate
            for candidate in decision_result.get("ranked_candidates", [])
            if candidate.get("sku_id") == previous_sku_id
        ),
        None,
    )
    if previous_sku is None:
        return None

    label = increased_dimension.replace("_", " ")
    return (
        f"Now that {label} matters more, {selected_sku.get('name')} moves ahead "
        f"of {previous_sku.get('name')} for what you're looking for."
    )


def build_decision_explanation(
    decision_result: Dict[str, Any], structured_facts: Dict[str, Any]
) -> str:
    """Build a correct local explanation from represented facts only."""
    if decision_result.get("decision") == "BLOCK":
        labels = {
            "size_constraint": "requested mattress size",
            "max_price": "maximum price",
            "latex_constraint": "latex exclusion",
            "require_CA_haul_away": "California haul-away requirement",
            "unknown_size_constraint": "verified size availability",
            "unknown_max_price": "verified price",
            "unknown_latex_constraint": "verified latex information",
            "unknown_require_CA_haul_away": "verified California haul-away availability",
        }
        constraints = [
            labels[item]
            for item in decision_result.get("violations", [])
            if item in labels
        ]
        if constraints:
            return (
                "I couldn't find a mattress that matches all of your current "
                "requirements: " + ", ".join(constraints) + "."
            )
        return "I couldn't find a mattress that matches all of your current requirements."

    selected = decision_result.get("selected_sku")
    if not selected:
        return "No recommendation is available."

    name = selected.get("name", "The selected mattress")
    lines = [f"### {name}", "", f"{name} is the top match based on your current preferences."]
    price = selected.get("price")
    max_price = structured_facts.get("max_price")
    if max_price is None:
        max_price = structured_facts.get("user_preferences", {}).get("max_price")
    if price is not None:
        price_line = f"- Price: ${price:,}"
        if max_price is not None and price <= max_price:
            price_line += f", within your ${max_price:,.0f} maximum"
        lines.append(price_line + ".")
    for field in ("firmness", "support", "cooling", "motion_isolation"):
        if field in selected:
            lines.append(f"- {field.replace('_', ' ').title()}: {selected[field]}/10.")

    if "haul_away_CA_available" in selected:
        availability = "available" if selected["haul_away_CA_available"] else "not available"
        lines.extend(
            ["", f"California haul-away is listed as {availability} for this mattress."]
        )

    rank_change = build_rank_change_explanation(decision_result)
    if rank_change:
        lines.extend(["", rank_change])
    return "\n".join(lines)


def build_customer_explanation(
    selected_sku: Optional[Dict[str, Any]], structured_facts: Dict[str, Any]
) -> str:
    """Compatibility wrapper for callers without a complete decision result."""
    result = structured_facts.get("decision_result") or {
        "decision": "ALLOW" if selected_sku else "BLOCK",
        "selected_sku": selected_sku,
        "violations": [],
        "metadata": {},
    }
    return build_decision_explanation(result, structured_facts)


def _model_output(
    client: Any,
    config: ModelConfiguration,
    prompt: Dict[str, Any],
    instruction: str,
) -> str:
    if hasattr(client, "responses"):
        response = client.responses.create(
            **responses_request_options(config),
            input=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(prompt)},
            ],
        )
        return response.output_text
    response = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    return response.choices[0].message.content


BASE_INSTRUCTION = load_customer_prompt("recommendation_explanation.md")
RETRY_INSTRUCTION = f"{BASE_INSTRUCTION}\n\n{load_prompt('grounded_retry.md')}"


def get_explanation(
    selected_sku: Optional[Dict[str, Any]],
    structured_facts: Dict[str, Any],
    decision_result: Optional[Dict[str, Any]] = None,
    *,
    catalog: Optional[Iterable[Dict[str, Any]]] = None,
    grounding_audit: Optional[Dict[str, Any]] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate, validate once, retry at most once, then fall back locally."""
    result = decision_result or structured_facts.get("decision_result") or {
        "decision": "ALLOW" if selected_sku else "BLOCK",
        "reason": "valid_recommendation" if selected_sku else "no_valid_sku",
        "selected_sku": selected_sku,
        "violations": [],
        "ranked_candidates": [selected_sku] if selected_sku else [],
        "metadata": {},
    }
    preferences = structured_facts.get("user_preferences", structured_facts)
    evidence = build_recommendation_evidence(
        result,
        preferences,
        approved_relaxation=structured_facts.get("approved_relaxation"),
    )
    validation_catalog = list(catalog or result.get("ranked_candidates") or [])
    if selected_sku and not validation_catalog:
        validation_catalog = [selected_sku]
    product_refs = known_product_references(validation_catalog)
    audit: Dict[str, Any] = {
        "authoritative_sources": evidence["authoritative_sources"],
        "grounding_evidence": evidence,
        "selected_sku_id": evidence["ranking_context"]["selected_sku_id"],
        "ranking_result": {
            "decision": result.get("decision"),
            "selected_sku_id": evidence["ranking_context"]["selected_sku_id"],
            "candidate_count": evidence["ranking_context"]["candidate_count"],
        },
        "validation": {"status": "not_run", "attempts": []},
        "retry": {"attempted": False},
        "fallback": {"used": False},
    }

    def finish(text: str) -> str:
        if grounding_audit is not None:
            grounding_audit.clear()
            grounding_audit.update(audit)
        return text

    if result.get("decision") == "BLOCK":
        audit["validation"]["status"] = "deterministic"
        audit["fallback"] = {"used": True, "reason": "blocked_outcome"}
        return finish(build_decision_explanation(result, structured_facts))

    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        audit["validation"]["status"] = "deterministic"
        audit["fallback"] = {"used": True, "reason": "model_unavailable"}
        return finish(build_decision_explanation(result, structured_facts))

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    config = model_configuration(ModelTask.FAST_GROUNDED_GENERATION)
    prompt = {
        "task": "explain_authoritative_decision",
        "conversation_context": conversation_context or {},
        "grounding_evidence": evidence,
    }
    for attempt, instruction in enumerate((BASE_INSTRUCTION, RETRY_INSTRUCTION), start=1):
        if attempt == 2:
            audit["retry"] = {"attempted": True, "reason": "grounding_validation_failed"}
        log_event(f"EXPLANATION_PROMPT_SENT_ATTEMPT_{attempt}")
        try:
            output_text = _model_output(client, config, prompt, instruction)
        except Exception as error:
            audit["validation"]["attempts"].append(
                {"attempt": attempt, "valid": False, "reasons": ["generation_error"]}
            )
            audit["generation_error"] = type(error).__name__
            break
        validation = validate_recommendation_text(output_text, evidence, product_refs)
        if contains_internal_language(output_text):
            validation["valid"] = False
            validation["reasons"].append("internal_customer_language")
        audit["validation"]["attempts"].append({"attempt": attempt, **validation})
        if validation["valid"]:
            audit["validation"]["status"] = "passed"
            audit["fallback"] = {"used": False}
            log_event(f"EXPLANATION_VALIDATED_ATTEMPT_{attempt}")
            return finish(output_text)
        log_event(f"EXPLANATION_GROUNDING_FAILED_ATTEMPT_{attempt}")

    audit["validation"]["status"] = "failed"
    audit["fallback"] = {"used": True, "reason": "grounding_validation_failed"}
    return finish(build_decision_explanation(result, structured_facts))
