#!/usr/bin/env python3
"""Run the small Luna-vs-Terra model-selection experiment.

This is deliberately a small experiment, not the formal evaluation suite. It
uses the production extraction schema, prompts, grounding validators, and
validation-buffered generation boundary.
"""

import argparse
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.conversational_response import (
    BASE_INSTRUCTION,
    _response_payload,
    _validate_response,
)
from engine.data import SKU_CATALOG
from engine.grounding import build_recommendation_evidence
from engine.model_config import ModelConfiguration, ModelTask, responses_request_options
from engine.preference_extraction import (
    PREFERENCE_UPDATE_SCHEMA,
    SYSTEM_PROMPT,
    merge_preference_state,
    new_preference_state,
    validate_preference_update,
)
from engine.response_strategy import (
    build_comparison,
    build_review_fact,
    build_service_fact,
    render_comparison,
    render_review_fact,
    render_service_fact,
)
from engine.review_data import review_slice
from engine.decision import evaluate_decision


FIXTURE_PATH = ROOT / "fixtures" / "luna_vs_terra.json"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts"
    / "model-selection"
    / "luna-vs-terra"
    / "v1"
    / "2026-08-26_results.json"
)

PRICING = {
    "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20},
    "gpt-5.6-terra": {"input": 2.00, "cached_input": 0.20, "output": 12.00},
}
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"

CONFIGURATIONS = {
    ModelTask.STRUCTURED_UNDERSTANDING.value: [
        ModelConfiguration(ModelTask.STRUCTURED_UNDERSTANDING, "gpt-5.6-luna", "none"),
        ModelConfiguration(ModelTask.STRUCTURED_UNDERSTANDING, "gpt-5.6-terra", "none"),
    ],
    ModelTask.CONVERSATIONAL_REASONING.value: [
        ModelConfiguration(ModelTask.CONVERSATIONAL_REASONING, "gpt-5.6-luna", "low"),
        ModelConfiguration(ModelTask.CONVERSATIONAL_REASONING, "gpt-5.6-terra", "low"),
    ],
    ModelTask.FAST_GROUNDED_GENERATION.value: [
        ModelConfiguration(ModelTask.FAST_GROUNDED_GENERATION, "gpt-5.6-luna", "none"),
        ModelConfiguration(ModelTask.FAST_GROUNDED_GENERATION, "gpt-5.6-terra", "none"),
    ],
}

MANUAL_COMPARISONS = {
    "conversation_fuzzy_preference": {
        "terra_score": 3,
        "preference": "tie",
        "meaningful_difference": False,
        "rationale": "Both ask the same focused question and offer equally useful ways to describe the disliked feel.",
    },
    "conversation_priority_change": {
        "terra_score": 3,
        "preference": "tie",
        "meaningful_difference": False,
        "rationale": "Both acknowledge the spouse context, update the priority, and explain the practical consequence with comparable brevity.",
    },
    "conversation_no_match": {
        "terra_score": 3,
        "preference": "tie",
        "meaningful_difference": False,
        "rationale": "Both preserve the hard ceiling, identify the grounded $1,349 alternative, and ask for permission before relaxing anything.",
    },
    "conversation_catalog_review_disagreement": {
        "terra_score": 3,
        "preference": "tie",
        "meaningful_difference": False,
        "rationale": "Both clearly separate the listed 6/10 firmness from mixed owner experience; Terra's extra wording does not improve the decision.",
    },
    "fast_comparison_framing": {
        "terra_score": 3,
        "preference": "prefer_luna",
        "meaningful_difference": True,
        "rationale": "Luna's compact table makes the represented ratings and $149 tradeoff faster to scan; Terra is grounded but less directly comparable.",
    },
    "fast_review_summary": {
        "terra_score": 3,
        "preference": "prefer_terra",
        "meaningful_difference": True,
        "rationale": "Terra directly says owners generally do not report sleeping hot; Luna's opening 'Yes' is ambiguous against the shopper's question.",
    },
    "fast_product_explanation": {
        "terra_score": 2,
        "preference": "tie",
        "meaningful_difference": False,
        "rationale": "Terra is modestly shorter, but both add secondary details beyond the core fit explanation and remain longer than necessary.",
    },
    "fast_factual_response": {
        "terra_score": 3,
        "preference": "tie",
        "meaningful_difference": False,
        "rationale": "Both answer the represented California haul-away fact directly and add no unsupported service claim.",
    },
}


def _expanded_state(partial: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state = new_preference_state()
    for key, value in (partial or {}).items():
        if isinstance(value, dict) and isinstance(state.get(key), dict):
            state[key].update(deepcopy(value))
        else:
            state[key] = deepcopy(value)
    return state


def _path(value: Dict[str, Any], dotted: str) -> Any:
    current: Any = value
    for part in dotted.split("."):
        current = current[part]
    return current


def _usage(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if usage is None:
        return {}

    def field(name: str, default: int = 0) -> int:
        if isinstance(usage, dict):
            return int(usage.get(name, default) or default)
        return int(getattr(usage, name, default) or default)

    cached = 0
    details = usage.get("input_tokens_details") if isinstance(usage, dict) else getattr(usage, "input_tokens_details", None)
    if details:
        cached = int(details.get("cached_tokens", 0) if isinstance(details, dict) else getattr(details, "cached_tokens", 0) or 0)
    return {
        "input_tokens": field("input_tokens"),
        "cached_input_tokens": cached,
        "output_tokens": field("output_tokens"),
        "total_tokens": field("total_tokens"),
    }


def _cost(model: str, usage: Dict[str, int]) -> Optional[float]:
    rates = PRICING.get(model)
    if not rates or not usage:
        return None
    cached = usage.get("cached_input_tokens", 0)
    uncached = max(0, usage.get("input_tokens", 0) - cached)
    total = (
        uncached * rates["input"]
        + cached * rates["cached_input"]
        + usage.get("output_tokens", 0) * rates["output"]
    ) / 1_000_000
    return round(total, 8)


def _preserve_unselected_results(
    output: Path,
    fixture_version: str,
    selected_models: set[str],
) -> list[Dict[str, Any]]:
    if not selected_models or not output.exists():
        return []
    existing = json.loads(output.read_text(encoding="utf-8"))
    if existing.get("fixture_version") != fixture_version:
        raise RuntimeError(
            "Existing bakeoff artifact uses a different fixture version; "
            "refusing to merge live results"
        )
    return [
        result
        for result in existing.get("results", [])
        if result.get("model") not in selected_models
    ]


def _structured_result(client: OpenAI, case: Dict[str, Any], config: ModelConfiguration) -> Dict[str, Any]:
    state = _expanded_state(case.get("current_state"))
    started = perf_counter()
    response = client.responses.create(
        **responses_request_options(config),
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"current_state": state, "latest_user_message": case["message"]}),
            },
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
    total_ms = round((perf_counter() - started) * 1000, 3)
    raw = response.output_text
    reasons = []
    schema_valid = True
    try:
        update = json.loads(raw)
        validate_preference_update(update)
    except Exception as error:
        schema_valid = False
        update = None
        reasons.append(f"schema:{type(error).__name__}")

    if update is not None:
        merged = merge_preference_state(state, update)
        for dotted, expected in case.get("expected", {}).items():
            if _path(update, dotted) != expected:
                reasons.append(f"expected:{dotted}")
        for dotted, expected in case.get("preserve", {}).items():
            if _path(merged, dotted) != expected:
                reasons.append(f"state_preservation:{dotted}")
        relation = case.get("expected_relation")
        if relation:
            levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            left = levels.get(_path(update, relation[0]), 0)
            right = levels.get(_path(update, relation[2]), 0)
            if relation[1] == ">" and not left > right:
                reasons.append("expected_priority_relation")
    usage = _usage(response)
    return {
        "raw_output": raw,
        "parsed_output": update,
        "schema_valid": schema_valid,
        "automatic_pass": schema_valid and not reasons,
        "failure_reasons": reasons,
        "latency_ms": {"extraction": total_ms, "total": total_ms},
        "usage": usage or None,
        "estimated_cost_usd": _cost(config.model, usage),
    }


def _base_turn(strategy: str, fallback: str, grounding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent": "recommend",
        "response_strategy": strategy,
        "preference_state": {},
        "state_changes": {},
        "presentation": None,
        "grounding_data": grounding,
        "grounding_evidence": None,
        "recovery": None,
        "decision_result": None,
        "response_text": fallback,
    }


def _generation_scenario(name: str) -> Tuple[Dict[str, Any], str, Iterable[Dict[str, Any]]]:
    catalog = SKU_CATALOG
    if name == "fuzzy_preference":
        message = "I just don't want something that feels like my current mattress."
        fallback = "What feels wrong about your current mattress—too much sinking, hard to move on, too warm, too firm, or something else?"
        turn = _base_turn("clarification", fallback, {"recovery_type": "clarification", "message": fallback})
        turn["recovery"] = turn["grounding_data"]
        return turn, message, catalog
    if name == "priority_change":
        message = "Actually motion isolation matters more. My wife moves around constantly."
        fallback = "I'll prioritize limiting movement transfer now and treat cooling as secondary."
        turn = _base_turn("clarification", fallback, {"recovery_type": "clarification", "message": fallback})
        turn["preference_state"] = {"priorities": {"motion_isolation": "critical", "cooling": "medium"}}
        turn["state_changes"] = {"priorities": {"motion_isolation": {"before": "medium", "after": "critical"}}}
        turn["recovery"] = turn["grounding_data"]
        return turn, message, catalog
    if name == "no_match":
        message = "I need a king with California haul-away and $900 is my absolute max."
        fallback = "I'm not finding a fit at $900. The closest option that keeps the other requirements is $1,349. Should I show it, or keep the limit?"
        recovery = {"message": fallback, "requires_user_approval": True, "options": [{"price": 1349}]}
        turn = _base_turn("no_match_recovery", fallback, {"decision_result": {"decision": "BLOCK"}, "recovery": recovery})
        turn.update({"recovery": recovery, "decision_result": {"decision": "BLOCK"}, "preference_state": {"hard_constraints": {"max_price": 900}}})
        return turn, message, catalog
    if name in {"catalog_review_disagreement", "review_summary"}:
        message = "How firm do owners find Metro Cool Comfort?" if name == "catalog_review_disagreement" else "Do owners think Metro Cool Comfort sleeps hot?"
        topic = "firmness" if name == "catalog_review_disagreement" else "cooling"
        review = build_review_fact(["Metro Cool Comfort"], topic, catalog)
        fallback = render_review_fact(review)
        turn = _base_turn("review_evidence_lookup", fallback, review)
        turn["intent"] = "product_question"
        if name == "catalog_review_disagreement":
            product = next(item for item in catalog if item["sku_id"] == "S06")
            review["catalog_context"] = [{"name": product["name"], "firmness": product["firmness"]}]
        return turn, message, catalog
    if name == "comparison":
        message = "Compare Metro Cool Comfort and Urban Rest Core for me."
        grounding = build_comparison(["Metro Cool Comfort", "Urban Rest Core"], catalog)
        turn = _base_turn("catalog_comparison", render_comparison(grounding), grounding)
        turn["intent"] = "compare"
        turn["preference_state"] = {"priorities": {"cooling": "high", "price": "medium"}}
        return turn, message, catalog
    if name == "product_explanation":
        message = "Why might this work for me?"
        preferences = {"requested_size": "queen", "max_price": 1500, "exclude_latex": True, "cooling_preference": 9, "priorities": {"cooling": "critical"}}
        decision = evaluate_decision(preferences, catalog)
        evidence = build_recommendation_evidence(decision, preferences)
        selected = decision["selected_sku"]
        fallback = f"{selected['name']} is the strongest represented fit for your current requirements and cooling preference."
        turn = _base_turn("recommendation_pipeline", fallback, decision)
        turn.update({"decision_result": decision, "grounding_evidence": evidence, "preference_state": preferences})
        return turn, message, catalog
    if name == "service_fact":
        message = "Does Polar Motion Elite include haul-away in California?"
        fact = build_service_fact(["Polar Motion Elite"], catalog, service_attribute="haul_away")
        turn = _base_turn("service_fact_lookup", render_service_fact(fact), fact)
        turn["intent"] = "service_question"
        return turn, message, catalog
    raise ValueError(f"Unknown generation scenario: {name}")


def _generation_result(client: OpenAI, case: Dict[str, Any], config: ModelConfiguration) -> Dict[str, Any]:
    turn, message, catalog = _generation_scenario(case["scenario"])
    payload = _response_payload(turn, message, [], turn["response_text"])
    started = perf_counter()
    first_token_at = None
    completed_response = None
    deltas = []
    events = client.responses.create(
        **responses_request_options(config),
        stream=True,
        input=[
            {"role": "system", "content": BASE_INSTRUCTION},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    for event in events:
        event_type = getattr(event, "type", None)
        if event_type == "response.output_text.delta":
            if first_token_at is None:
                first_token_at = perf_counter()
            deltas.append(str(getattr(event, "delta", "")))
        elif event_type == "response.completed":
            completed_response = getattr(event, "response", None)
    completed_at = perf_counter()
    raw = "".join(deltas).strip()
    validation = _validate_response(raw, turn, catalog)
    usage = _usage(completed_response)
    return {
        "raw_output": raw,
        "grounding_validation": validation,
        "automatic_pass": validation["valid"],
        "manual_rubric_score_0_to_3": None,
        "manual_review_status": "pending",
        "review_for": case["review_for"],
        "latency_ms": {
            "generation_ttft": round((first_token_at - started) * 1000, 3) if first_token_at else None,
            "generation_total": round((completed_at - started) * 1000, 3),
            "validated_visible": round((completed_at - started) * 1000, 3),
        },
        "usage": usage or None,
        "estimated_cost_usd": _cost(config.model, usage),
    }


def run(output: Path, models: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; no live bakeoff was run")
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    selected_models = set(models or ())
    preserved_results = _preserve_unselected_results(
        output,
        fixture["version"],
        selected_models,
    )
    results = []
    for case in fixture["cases"]:
        for config in CONFIGURATIONS[case["task"]]:
            if selected_models and config.model not in selected_models:
                continue
            base = {
                "case_id": case["id"],
                "task": case["task"],
                "model": config.model,
                "reasoning_effort": config.reasoning_effort,
            }
            try:
                measured = _structured_result(client, case, config) if case["task"] == ModelTask.STRUCTURED_UNDERSTANDING.value else _generation_result(client, case, config)
                base.update(measured)
            except Exception as error:
                base.update({"automatic_pass": False, "error": type(error).__name__, "error_message": str(error)})
            results.append(base)
    artifact = {
        "status": "live_run_complete_manual_review_pending",
        "fixture_version": fixture["version"],
        "quality_bars": fixture["quality_bars"],
        "pricing_source": PRICING_SOURCE,
        "results": preserved_results + results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def finalize_manual_comparison(output: Path) -> Dict[str, Any]:
    artifact = json.loads(output.read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in fixture["cases"]}
    results = {
        (result["case_id"], result["model"]): result
        for result in artifact["results"]
    }
    comparisons = []
    for case_id, review in MANUAL_COMPARISONS.items():
        luna = results[(case_id, "gpt-5.6-luna")]
        terra = results[(case_id, "gpt-5.6-terra")]
        terra["manual_rubric_score_0_to_3"] = review["terra_score"]
        terra["manual_review_status"] = "completed_against_same_evaluation_rubric"
        turn, message, _ = _generation_scenario(cases[case_id]["scenario"])
        comparisons.append(
            {
                "case_id": case_id,
                "shopper_message": message,
                "fixture_reference": cases[case_id].get("fixture_reference"),
                "input_context": _response_payload(turn, message, [], turn["response_text"]),
                "luna_raw_output": luna["raw_output"],
                "terra_raw_output": terra["raw_output"],
                "luna_rubric_score_0_to_3": luna["manual_rubric_score_0_to_3"],
                "terra_rubric_score_0_to_3": review["terra_score"],
                "luna_grounding": luna["grounding_validation"],
                "terra_grounding": terra["grounding_validation"],
                "meaningful_difference": review["meaningful_difference"],
                "preference": review["preference"],
                "rationale": review["rationale"],
            }
        )
    preference_counts = {
        preference: sum(item["preference"] == preference for item in comparisons)
        for preference in ("prefer_luna", "prefer_terra", "tie")
    }
    artifact["status"] = "live_run_complete_manual_review_complete"
    artifact["manual_review_method"] = {
        "type": "non_blind_side_by_side",
        "reason": "The existing harness has no blind-review facility; no new infrastructure was added solely for blinding.",
        "criteria": "docs/EVALUATION.md",
    }
    artifact["qualitative_comparisons"] = comparisons
    artifact["preference_counts"] = preference_counts
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--model",
        action="append",
        choices=sorted({config.model for configs in CONFIGURATIONS.values() for config in configs}),
        help="Run only this candidate model; repeat to select more than one.",
    )
    parser.add_argument(
        "--finalize-review",
        action="store_true",
        help="Record the completed Luna/Terra manual comparison without making API calls.",
    )
    args = parser.parse_args()
    if args.finalize_review:
        artifact = finalize_manual_comparison(args.output)
        print(f"Finalized {len(artifact['qualitative_comparisons'])} qualitative comparisons in {args.output}")
        return 0
    try:
        artifact = run(args.output, models=args.model)
    except RuntimeError as error:
        print(str(error))
        return 2
    print(f"Wrote {len(artifact['results'])} measured case/configuration results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
