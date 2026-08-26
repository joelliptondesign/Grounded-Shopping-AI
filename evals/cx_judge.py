"""Structured model judge for the independent Shopping Experience evaluation."""

import json
import os
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CX_JUDGE_MODEL = "gpt-5.6-sol"
DEFAULT_CX_JUDGE_REASONING = "high"
CX_CRITERIA = (
    "natural_understanding",
    "conversational_autonomy",
    "forward_momentum",
    "clarification_restraint",
    "alternative_usefulness",
    "context_continuity",
    "customer_language",
    "tone",
    "decision_support",
    "information_density",
    "presentation_usefulness",
    "budget_judgment",
    "appropriate_certainty",
    "shortlist_usefulness",
)


def cx_judge_configuration() -> Dict[str, str]:
    """Resolve an offline-only judge route without changing production routing."""
    return {
        "model": os.getenv("SHOPPING_CX_JUDGE_MODEL", DEFAULT_CX_JUDGE_MODEL),
        "reasoning_effort": os.getenv(
            "SHOPPING_CX_JUDGE_REASONING", DEFAULT_CX_JUDGE_REASONING
        ),
    }


def _criterion_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "applicable": {"type": "boolean"},
            "score": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
            "rationale": {"type": "string"},
        },
        "required": ["applicable", "score", "rationale"],
        "additionalProperties": False,
    }


CX_JUDGE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        **{name: _criterion_schema() for name in CX_CRITERIA},
        "overall_score": {"type": "integer", "minimum": 0, "maximum": 3},
        "overall_rationale": {"type": "string"},
        "biggest_customer_experience_issue": {"type": "string"},
    },
    "required": [
        *CX_CRITERIA,
        "overall_score",
        "overall_rationale",
        "biggest_customer_experience_issue",
    ],
    "additionalProperties": False,
}


CX_RUBRIC = {
    "scale": {
        "0": "Failure: substantially fails as a shopping experience.",
        "1": "Weak: functions but is procedural, awkward, rigid, interrogative, or unhelpful.",
        "2": "Good: competent modern shopping assistance that understands and advances the decision.",
        "3": "Excellent: polished consumer AI shopping with especially strong judgment, continuity, tradeoff framing, low effort, or presentation.",
    },
    "criteria": {
        "natural_understanding": "Understands normal shopper meaning without artificial precision.",
        "conversational_autonomy": "Makes reasonable shopping decisions without handing avoidable work back.",
        "forward_momentum": "Shows options, compares, or otherwise advances the task when possible.",
        "clarification_restraint": "Asks only when missing information materially prevents usefulness.",
        "alternative_usefulness": "Makes near matches and their tradeoffs useful when perfection is unavailable.",
        "context_continuity": "Resolves natural references and treats the conversation as cumulative.",
        "customer_language": "Uses normal shopping language and hides implementation concepts.",
        "tone": "Natural, friendly, relaxed, competent, and neither robotic nor salesy.",
        "decision_support": "Explains fit, meaningful differences, tradeoffs, and useful next considerations.",
        "information_density": "Provides useful detail without repetition, buried answers, or specification dumping.",
        "presentation_usefulness": "Uses conversation and structured presentation to make the task easier.",
        "budget_judgment": "Makes sensible use of the shopper's budget without mechanically minimizing or maximizing spend.",
        "appropriate_certainty": "Uses a strong pick only when preferences distinguish one; otherwise frames a useful exploratory shortlist without false certainty.",
        "shortlist_usefulness": "Selected options are plausible, meaningfully differentiated, non-redundant, and useful for the next decision.",
    },
}


def _turns_from_actual(actual: Dict[str, Any]) -> List[Dict[str, Any]]:
    turns = []
    for item in actual.get("turns", []):
        turn = item.get("turn", item)
        turns.append(
            {
                "shopper": item.get("user") or turn.get("user_message"),
                "assistant": item.get("final_shopper_response")
                or turn.get("final_shopper_response")
                or turn.get("response_text")
                or (turn.get("presentation") or {}).get("message"),
                "shopper_state": deepcopy(
                    item.get("parsed_state") or turn.get("preference_state")
                ),
                "authoritative_product_result": deepcopy(
                    item.get("decision_result") or turn.get("decision_result")
                ),
                "shopping_selection": deepcopy(
                    item.get("shopping_selection") or turn.get("shopping_selection")
                ),
                "represented_evidence": deepcopy(
                    item.get("grounding_evidence")
                    or turn.get("grounding_evidence")
                    or turn.get("grounding_data")
                ),
                "presentation_contract": deepcopy(
                    item.get("presentation_contract") or turn.get("presentation")
                ),
            }
        )
    return turns


def build_cx_judge_payload(
    case: Dict[str, Any], actual: Dict[str, Any]
) -> Dict[str, Any]:
    """Expose available shopping context without evaluator implementation internals."""
    turns = _turns_from_actual(actual)
    gold_intent: List[Any] = []
    for turn in case.get("turns", []):
        if turn.get("qualitative"):
            gold_intent.append(deepcopy(turn["qualitative"]))
    if case.get("qualitative"):
        gold_intent.append(deepcopy(case["qualitative"]))
    return {
        "case_id": case["case_id"],
        "journey": turns,
        "gold_behavioral_intent": gold_intent,
        "shopping_experience_rubric": CX_RUBRIC,
    }


def validate_cx_judgment(judgment: Dict[str, Any]) -> None:
    for name in CX_CRITERIA:
        item = judgment.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"Missing CX criterion {name}")
        applicable = item.get("applicable")
        score = item.get("score")
        if not isinstance(applicable, bool):
            raise ValueError(f"Invalid applicability for {name}")
        if applicable and (not isinstance(score, int) or score not in range(4)):
            raise ValueError(f"Invalid score for applicable criterion {name}")
        if not applicable and score is not None:
            raise ValueError(f"N/A criterion {name} must use a null score")
        if not item.get("rationale"):
            raise ValueError(f"Missing rationale for {name}")
    if judgment.get("overall_score") not in range(4):
        raise ValueError("Invalid overall CX score")
    if not judgment.get("overall_rationale"):
        raise ValueError("Missing overall CX rationale")
    if not judgment.get("biggest_customer_experience_issue"):
        raise ValueError("Missing biggest CX issue")


def judge_shopping_experience(
    client: Any,
    payload: Dict[str, Any],
    *,
    instruction: Optional[str] = None,
) -> Dict[str, Any]:
    config = cx_judge_configuration()
    system_instruction = instruction or (
        ROOT / "prompts" / "shopping_experience_judge.md"
    ).read_text(encoding="utf-8")
    started = time.perf_counter()
    response = client.responses.create(
        model=config["model"],
        reasoning={"effort": config["reasoning_effort"]},
        input=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": json.dumps(payload)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "shopping_experience_judgment",
                "schema": CX_JUDGE_SCHEMA,
                "strict": True,
            }
        },
    )
    judgment = json.loads(response.output_text)
    validate_cx_judgment(judgment)
    usage = getattr(response, "usage", None)
    usage_data = usage.model_dump() if hasattr(usage, "model_dump") else str(usage or "")
    return {
        "configuration": config,
        "judgment": judgment,
        "raw_model_output": response.output_text,
        "usage": usage_data,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "human_calibration_status": "pending",
    }


def cx_summary(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    judgments = [item["judgment"] for item in results]
    criterion_scores: Dict[str, Dict[str, Any]] = {}
    for name in CX_CRITERIA:
        scores = [
            item[name]["score"] for item in judgments if item[name]["applicable"]
        ]
        criterion_scores[name] = {
            "scored_cases": len(scores),
            "average": round(sum(scores) / len(scores), 3) if scores else None,
        }
    overall = [item["overall_score"] for item in judgments]
    return {
        "judged_cases": len(judgments),
        "overall_average": round(sum(overall) / len(overall), 3) if overall else None,
        "criteria": criterion_scores,
    }
