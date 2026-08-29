#!/usr/bin/env python3
"""Run deterministic or live product evaluations and write inspectable artifacts."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response
from engine.data import CATALOG_FIXTURE_VERSION, SKU_CATALOG
from engine.decision import constraint_violations, evaluate_decision
from engine.grounding import (
    build_recommendation_evidence,
    known_product_references,
    validate_recommendation_text,
    validate_review_text,
)
from engine.model_config import DEFAULT_MODELS, DEFAULT_REASONING
from engine.preference_extraction import (
    merge_preference_state,
    new_preference_state,
    validate_preference_update,
)
from engine.response_strategy import build_review_fact
from engine.review_data import REVIEW_FIXTURE_VERSION
from evals.scoring import CaseResult, flatten, markdown_report, nested_get, summary
from evals.cx_judge import (
    CX_CRITERIA,
    build_cx_judge_payload,
    cx_judge_configuration,
    cx_summary,
    judge_shopping_experience,
)
from evals.system_integrity import actual_turns, evaluate_system_integrity


SCHEMA_VERSION = "1.0"
SUITE_ID = "shopping-agent-core"
SUITE_NAME = "Shopping Agent Core"
SUITE_VERSION = "v2"
SUITE_DIR = ROOT / "evals" / SUITE_ID / SUITE_VERSION
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "evals" / SUITE_ID / SUITE_VERSION
EVAL_INDEX = ROOT / "artifacts" / "evals" / "INDEX.md"
DIMENSIONS = {
    "understanding",
    "decision_correctness",
    "grounding",
    "conversation_quality",
    "presentation",
    "robustness_and_recovery",
}
INVARIANTS = {
    "never_recommend_ineligible_product",
    "never_silently_relax_hard_requirement",
    "never_present_unknown_service_as_known",
    "never_invent_product_facts",
    "never_invent_review_evidence",
    "generated_language_cannot_replace_winner",
    "generated_language_cannot_replace_selection",
    "preserve_state_after_extraction_failure",
    "never_treat_missing_evidence_as_false",
}

API_PRICING_PER_MILLION = {
    "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20},
    "gpt-5.6-sol": {"input": 4.00, "cached_input": 0.40, "output": 20.00},
}
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"


def complete_update(partial: Dict[str, Any]) -> Dict[str, Any]:
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
            "explicit_browse_intent": False,
        },
        "recovery_response": "none",
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
        # Existing v2 fixtures predate cold-start readiness. Keep their prior
        # behavior unless a focused cold-start case opts into another level.
        "recommendation_readiness": "exploratory",
    }
    for key, value in partial.items():
        if isinstance(value, dict) and isinstance(update.get(key), dict):
            update[key].update(deepcopy(value))
        else:
            update[key] = deepcopy(value)
    if "shopping_action" not in partial:
        context = update["turn_context"]
        action = {
            "compare": "compare_products",
            "product_question": "answer_product_question",
            "service_question": "answer_service_question",
            "off_topic": "off_topic",
        }.get(update["intent"], "recommend_products")
        if update["intent"] == "recommend" and len(context["product_names"]) >= 2:
            action = "choose_from_products"
        update["shopping_action"] = {
            "action": action,
            "product_ids": list(context["product_names"]),
            "product_attribute": context["product_attribute"],
            "service_attribute": context["service_attribute"],
        }
    return update


class FixtureClient:
    def __init__(self, update: Dict[str, Any]):
        self.responses = self
        self.update = complete_update(update)

    def create(self, **_: Any) -> Any:
        return SimpleNamespace(output_text=json.dumps(self.update))


class ErrorClient:
    def __init__(self, message: str):
        self.responses = self
        self.message = message

    def create(self, **_: Any) -> Any:
        raise RuntimeError(self.message)


class RecordingResponses:
    def __init__(self, wrapped: Any, records: List[Dict[str, Any]]):
        self.wrapped = wrapped
        self.records = records

    def create(self, **kwargs: Any) -> Any:
        started = time.perf_counter()
        response = self.wrapped.create(**kwargs)
        usage = getattr(response, "usage", None)
        usage_data = usage.model_dump() if hasattr(usage, "model_dump") else str(usage or "")
        self.records.append(
            {
                "model": kwargs.get("model"),
                "raw_model_output": getattr(response, "output_text", ""),
                "usage": usage_data,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
        return response


class RecordingClient:
    def __init__(self, wrapped: Any):
        self.calls: List[Dict[str, Any]] = []
        self.responses = RecordingResponses(wrapped.responses, self.calls)


def load_documents() -> List[Dict[str, Any]]:
    documents = []
    for path in SUITE_DIR.glob("*.json"):
        if path.name == "manual_scores.json":
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        document["_path"] = str(path.relative_to(ROOT))
        documents.append(document)
    return documents


def validate_documents(documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    errors: List[str] = []
    seen = set()
    count = 0
    for document in documents:
        if document.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{document['_path']}: unsupported schema_version")
        if document.get("suite_id") != SUITE_ID:
            errors.append(f"{document['_path']}: unsupported suite_id")
        if document.get("suite_version") != SUITE_VERSION:
            errors.append(f"{document['_path']}: unsupported suite_version")
        for case in document.get("cases", []):
            count += 1
            case_id = case.get("case_id")
            if not case_id or case_id in seen:
                errors.append(f"{document['_path']}: duplicate or missing case_id {case_id}")
            seen.add(case_id)
            missing = {"category", "dimensions", "severity_if_failed", "tags"} - set(case)
            if missing:
                errors.append(f"{case_id}: missing {sorted(missing)}")
            unknown_dimensions = set(case.get("dimensions", [])) - DIMENSIONS
            if unknown_dimensions:
                errors.append(f"{case_id}: unknown dimensions {sorted(unknown_dimensions)}")
            if case.get("severity_if_failed") not in {"critical", "major", "minor"}:
                errors.append(f"{case_id}: invalid severity")
            suite = document.get("suite")
            kind = case.get("kind")
            if suite == "single_turn" and kind not in {"understanding", "decision", "grounding", "presentation", "qualitative"}:
                errors.append(f"{case_id}: invalid single-turn kind {kind}")
            if suite not in {"single_turn", "multi_turn"}:
                errors.append(f"{document['_path']}: invalid suite {suite}")
            required_by_kind = {
                "understanding": {"turns"},
                "qualitative": {"turns", "qualitative"},
                "decision": {"preferences", "expected"},
                "grounding": {"validator", "response", "expected_valid"},
                "presentation": {"user", "fixture_update", "expected"},
            }
            if suite == "single_turn":
                kind_missing = required_by_kind.get(kind, set()) - set(case)
                if kind_missing:
                    errors.append(f"{case_id}: missing kind fields {sorted(kind_missing)}")
            if suite == "multi_turn" and not case.get("turns"):
                errors.append(f"{case_id}: multi-turn case has no turns")
            if case.get("kind") == "understanding" or document.get("suite") == "multi_turn":
                for turn in case.get("turns", []):
                    try:
                        validate_preference_update(complete_update(turn.get("fixture_update", {})))
                    except ValueError as error:
                        errors.append(f"{case_id}: invalid fixture update: {error}")
            unknown_invariants = set(case.get("invariants", [])) - INVARIANTS
            if unknown_invariants:
                errors.append(f"{case_id}: unknown invariants {sorted(unknown_invariants)}")
    return {"valid": not errors, "errors": errors, "case_count": count}


def catalog_for(case: Dict[str, Any]) -> List[Dict[str, Any]]:
    if "catalog" in case:
        return deepcopy(case["catalog"])
    ids = case.get("catalog_sku_ids")
    if ids:
        return [deepcopy(item) for item in SKU_CATALOG if item["sku_id"] in ids]
    return deepcopy(SKU_CATALOG)


def make_result(case: Dict[str, Any]) -> CaseResult:
    return CaseResult(
        case_id=case["case_id"],
        category=case["category"],
        dimensions=case["dimensions"],
        severity=case["severity_if_failed"],
        tags=case["tags"],
    )


def compare_expected(result: CaseResult, actual: Dict[str, Any], expected: Dict[str, Any], prefix: str = "") -> None:
    for path, value in flatten(expected).items():
        criterion = f"{prefix}.{path}" if prefix else path
        result.check(criterion, value, nested_get(actual, path))


def core_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return the complete versioned shopper-state contract, excluding UI metadata."""
    return {
        "intent": state.get("intent"),
        "hard_constraints": deepcopy(state.get("hard_constraints", {})),
        "soft_preferences": deepcopy(state.get("soft_preferences", {})),
        "directions": deepcopy(state.get("directions", {})),
        "priorities": deepcopy(state.get("priorities", {})),
        "needs_clarification": bool(state.get("needs_clarification", False)),
        "clarification_question": state.get("clarification_question"),
        "clarification_reason": state.get("clarification_reason"),
        "recommendation_readiness": state.get("recommendation_readiness"),
    }


def gold_state_after_turn(
    before: Dict[str, Any], turn: Dict[str, Any], expected: Dict[str, Any]
) -> Dict[str, Any]:
    if turn.get("fixture_error"):
        gold = deepcopy(before)
    else:
        gold = merge_preference_state(before, complete_update(turn.get("fixture_update", {})))
    gold["intent"] = expected.get("intent", gold.get("intent"))
    for path, value in flatten(expected.get("state", {})).items():
        current = gold
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = deepcopy(value)
    return gold


def turn_with_update(
    message: str,
    update: Dict[str, Any],
    state: Dict[str, Any],
    catalog: List[Dict[str, Any]],
    previous: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return process_conversation_turn(
        message,
        deepcopy(state),
        catalog,
        client=FixtureClient(update),
        previous_decision_result=previous,
    )


def run_understanding(case: Dict[str, Any], live_client: Optional[Any]) -> CaseResult:
    result = make_result(case)
    state = deepcopy(case.get("initial_state") or new_preference_state())
    previous = None
    gold_state = deepcopy(state)
    outputs = []
    history: List[Dict[str, str]] = []
    for index, turn in enumerate(case["turns"], start=1):
        actual = process_conversation_turn(
            turn["user"],
            deepcopy(state),
            catalog_for(case),
            client=live_client or FixtureClient(turn.get("fixture_update", {})),
            previous_decision_result=previous,
            conversation_history=history,
        )
        expected = turn.get("expected", {})
        result.check(f"turn_{index}.intent", expected.get("intent"), actual["intent"])
        gold_state = gold_state_after_turn(gold_state, turn, expected)
        expected_state = core_state(gold_state)
        if expected.get("clarification_question_exact") is False:
            expected_state.pop("clarification_question", None)
        compare_expected(
            result,
            core_state(actual["preference_state"]),
            expected_state,
            f"turn_{index}.state",
        )
        if "modality" in expected:
            result.check(f"turn_{index}.modality", expected["modality"], actual["modality"])
        if "decision" in expected:
            result.check(f"turn_{index}.decision", expected["decision"], (actual.get("decision_result") or {}).get("decision"))
        if "winner" in expected:
            result.check(
                f"turn_{index}.winner",
                expected["winner"],
                (actual.get("decision_result") or {}).get("selected_sku", {}).get("sku_id"),
            )
        output: Dict[str, Any] = {"user": turn["user"], "turn": actual}
        if live_client is not None and case.get("qualitative"):
            audit: Dict[str, Any] = {}
            output["final_shopper_response"] = generate_turn_response(
                actual,
                turn["user"],
                catalog=catalog_for(case),
                client=live_client,
                audit=audit,
            )
            output["generation_audit"] = audit
        outputs.append(output)
        history.extend(
            [
                {"role": "user", "content": turn["user"]},
                {"role": "assistant", "content": actual.get("response_text") or actual["presentation"]["message"]},
            ]
        )
        state = actual["preference_state"]
        if actual.get("decision_result"):
            previous = actual["decision_result"]
    result.actual = {"turns": outputs, "qualitative_rubric": case.get("qualitative")}
    if case.get("qualitative"):
        result.qualitative_pending = True
    return result


def run_decision(case: Dict[str, Any]) -> CaseResult:
    result = make_result(case)
    catalog = catalog_for(case)
    actual = evaluate_decision(case["preferences"], catalog)
    expected = case["expected"]
    result.check("decision", expected["decision"], actual["decision"])
    if "candidate_ids" in expected:
        result.check("candidate_ids", expected["candidate_ids"], [item["sku_id"] for item in actual["ranked_candidates"]])
    if "candidate_set" in expected:
        result.check("candidate_set", sorted(expected["candidate_set"]), sorted(item["sku_id"] for item in actual["ranked_candidates"]))
    if "winner" in expected:
        result.check("winner", expected["winner"], (actual.get("selected_sku") or {}).get("sku_id"))
    if "violations" in expected:
        result.check("violations", sorted(expected["violations"]), sorted(actual.get("violations", [])))
    if "repeat_order" in expected:
        repeated = evaluate_decision(case["preferences"], catalog)
        result.check("repeat_order", [item["sku_id"] for item in actual["ranked_candidates"]], [item["sku_id"] for item in repeated["ranked_candidates"]])
    result.actual = {
        "decision_result": actual,
        "decision_preferences": deepcopy(case["preferences"]),
    }
    return result


def run_grounding(case: Dict[str, Any]) -> CaseResult:
    result = make_result(case)
    validator = case["validator"]
    if validator == "recommendation":
        decision = evaluate_decision(case["preferences"], catalog_for(case))
        evidence = build_recommendation_evidence(decision, case["preferences"])
        if case.get("remove_selected_fields") and evidence.get("selected_sku"):
            for field in case["remove_selected_fields"]:
                evidence["selected_sku"].pop(field, None)
            evidence["verified_services"]["CA_haul_away"] = {"verified": False, "available": None}
        actual = validate_recommendation_text(case["response"], evidence, known_product_references(catalog_for(case)))
    elif validator == "review":
        evidence = build_review_fact(case["product_names"], case.get("review_topic"), catalog_for(case))
        actual = validate_review_text(case["response"], evidence)
    else:
        raise ValueError(f"Unsupported grounding validator: {validator}")
    result.check("grounding.valid", case["expected_valid"], actual["valid"])
    for reason in case.get("expected_reasons", []):
        result.check(f"grounding.reason.{reason}", True, reason in actual["reasons"])
    result.actual = {"validation": actual}
    return result


def run_presentation(case: Dict[str, Any]) -> CaseResult:
    result = make_result(case)
    state = deepcopy(case.get("initial_state") or new_preference_state())
    actual = turn_with_update(case["user"], case["fixture_update"], state, catalog_for(case), None)
    expected = case["expected"]
    result.check("modality", expected["modality"], actual["modality"])
    if "product_ids" in expected:
        result.check("product_ids", expected["product_ids"], [item["sku_id"] for item in actual["presentation"]["products"]])
    if "first_row" in expected:
        rows = (actual["presentation"].get("comparison") or {}).get("rows", [])
        result.check("first_row", expected["first_row"], rows[0]["key"] if rows else None)
    if "actions" in expected:
        result.check("actions", expected["actions"], [item["action"] for item in actual["presentation"]["actions"]])
    if expected.get("suggested_replies"):
        result.check("suggested_replies_present", True, bool(actual["presentation"]["suggested_replies"]))
    result.actual = actual
    if case.get("qualitative"):
        result.qualitative_pending = True
    return result


def run_multi_turn(case: Dict[str, Any], live_client: Optional[Any]) -> CaseResult:
    result = make_result(case)
    state = deepcopy(case.get("initial_state") or new_preference_state())
    previous = None
    gold_state = deepcopy(state)
    history: List[Dict[str, str]] = []
    outputs = []
    for index, turn in enumerate(case["turns"], start=1):
        client = ErrorClient(turn["fixture_error"]) if turn.get("fixture_error") else (live_client or FixtureClient(turn.get("fixture_update", {})))
        actual = process_conversation_turn(
            turn["user"], state, catalog_for(case),
            client=client,
            previous_decision_result=previous,
            conversation_history=history,
        )
        expected = turn["expected"]
        result.check(f"turn_{index}.intent", expected["intent"], actual["intent"])
        result.check(f"turn_{index}.modality", expected["modality"], actual["modality"])
        gold_state = gold_state_after_turn(gold_state, turn, expected)
        if SUITE_VERSION == "v2":
            compare_expected(
                result,
                core_state(actual["preference_state"]),
                expected.get("state", {}),
                f"turn_{index}.state",
            )
        else:
            compare_expected(result, core_state(actual["preference_state"]), core_state(gold_state), f"turn_{index}.state")
        if "decision" in expected:
            result.check(f"turn_{index}.decision", expected["decision"], (actual.get("decision_result") or {}).get("decision"))
        if "winner" in expected:
            result.check(f"turn_{index}.winner", expected["winner"], (actual.get("decision_result") or {}).get("selected_sku", {}).get("sku_id"))
        if "recovery_type" in expected:
            result.check(f"turn_{index}.recovery_type", expected["recovery_type"], (actual.get("recovery") or {}).get("recovery_type"))
        if "extraction_error" in expected:
            result.check(f"turn_{index}.extraction_error", expected["extraction_error"], bool(actual.get("extraction_error")))
        response = actual.get("response_text") or actual["presentation"]["message"]
        audit: Dict[str, Any] = {}
        if live_client is not None:
            response = generate_turn_response(actual, turn["user"], history, catalog=catalog_for(case), client=live_client, audit=audit)
        outputs.append({"user": turn["user"], "input_state": state, "parsed_state": actual["preference_state"], "decision_preferences": actual.get("decision_preferences"), "decision_result": actual.get("decision_result"), "shopping_selection": actual.get("shopping_selection"), "grounding_evidence": actual.get("grounding_evidence") or actual.get("grounding_data"), "presentation_contract": actual["presentation"], "final_shopper_response": response, "timing": actual.get("timing"), "generation_audit": audit, "qualitative": turn.get("qualitative")})
        if turn.get("qualitative"):
            result.qualitative_pending = True
        history.extend([{"role": "user", "content": turn["user"]}, {"role": "assistant", "content": response}])
        state = actual["preference_state"]
        if actual.get("decision_result"):
            previous = actual["decision_result"]
    result.actual = {"turns": outputs}
    return result


def load_manual_scores(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    scores = {}
    for item in document.get("scores", []):
        score = item.get("score")
        rationale = item.get("rationale")
        if not isinstance(score, int) or score not in range(4) or not rationale:
            raise ValueError(f"Invalid manual score for {item.get('case_id')}")
        scores[item["case_id"]] = item
    return scores


def prompt_hashes() -> Dict[str, str]:
    hashes = {}
    for path in sorted((ROOT / "prompts").glob("*.md")):
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return hashes


def code_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def configuration_label(run: Dict[str, Any]) -> str:
    models = {
        item["model"]
        for item in run.get("configuration", {}).get("models", {}).values()
        if item.get("model")
    }
    if models == {"gpt-5.6-luna"}:
        return "Luna routing"
    if not models:
        return "No model routing"
    return ", ".join(sorted(models))


def write_eval_index(index_path: Path = EVAL_INDEX) -> None:
    artifact_root = ROOT / "artifacts" / "evals"
    rows = []
    for raw_path in sorted(artifact_root.glob("*/*/*_run.json"), reverse=True):
        run = json.loads(raw_path.read_text(encoding="utf-8"))
        report_path = raw_path.with_name(raw_path.name.replace("_run.json", "_report.md"))
        created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        totals = run["summary"]
        report_link = os.path.relpath(report_path, index_path.parent)
        raw_link = os.path.relpath(raw_path, index_path.parent)
        rows.append(
            "| {name} | {version} | {timestamp} | {mode} | {configuration} | "
            "{result} | [Report]({report}) | [Raw Results]({raw}) |".format(
                name=run.get("suite_name", run.get("suite_id", "Unknown")),
                version=run.get("suite_version", "Unknown"),
                timestamp=created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                mode=run["mode"].title(),
                configuration=configuration_label(run),
                result=f"{totals['passed']}/{totals['cases_run']} passed",
                report=report_link,
                raw=raw_link,
            )
        )
    content = "\n".join(
        [
            "# Evaluation Runs",
            "",
            "Immutable runs are organized by evaluation concept, definition version, and UTC execution timestamp.",
            "See the [evaluation framework](../../docs/EVALUATION.md) and [Shopping Agent Core suite](../../evals/shopping-agent-core/README.md).",
            "",
            "| Eval suite | Version | Run | Mode | Configuration | Result | Report | Raw |",
            "|---|---|---|---|---|---|---|---|",
            *rows,
            "",
        ]
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8")


def evaluate_case(case: Dict[str, Any], suite: str, live_client: Optional[Any]) -> CaseResult:
    if suite == "multi_turn":
        return run_multi_turn(case, live_client)
    kind = case["kind"]
    if kind == "understanding" or kind == "qualitative":
        return run_understanding(case, live_client)
    if kind == "decision":
        return run_decision(case)
    if kind == "grounding":
        return run_grounding(case)
    if kind == "presentation":
        return run_presentation(case)
    raise ValueError(f"Unsupported case kind: {kind}")


def _actual_turns(result: CaseResult) -> List[Dict[str, Any]]:
    actual = result.actual
    if "turns" not in actual:
        return [actual] if actual else []
    turns = []
    for item in actual["turns"]:
        turns.append(item.get("turn", item))
    return turns


def direct_invariant_outcome(invariant: str, result: CaseResult) -> Optional[bool]:
    """Score an invariant from its own evidence, not overall case success."""
    turns = _actual_turns(result)
    if invariant == "preserve_state_after_extraction_failure":
        failures = [turn for turn in turns if turn.get("extraction_error")]
        if not failures:
            return None
        return all(
            turn.get("preference_state") == turn.get("previous_preference_state")
            for turn in failures
        )
    if invariant in {
        "never_recommend_ineligible_product",
        "never_silently_relax_hard_requirement",
    }:
        recommendations = [turn for turn in turns if turn.get("shopping_selection")]
        if not recommendations:
            return None
        return all(
            all(
                not constraint_violations(
                    turn.get("decision_preferences") or {}, candidates[sku_id]
                )
                for sku_id in turn["shopping_selection"].get("selected_product_ids", [])
                if sku_id in candidates
            )
            for turn in recommendations
            for candidates in [{item.get("sku_id"): item for item in turn["decision_result"].get("ranked_candidates", [])}]
        )
    if invariant in {
        "generated_language_cannot_replace_winner",
        "generated_language_cannot_replace_selection",
    }:
        recommendations = [turn for turn in turns if turn.get("shopping_selection")]
        if not recommendations:
            return None
        return all(
            [
                item.get("sku_id")
                for item in (turn.get("presentation") or turn.get("presentation_contract") or {}).get("products", [])
            ]
            == turn["shopping_selection"].get("selected_product_ids", [])
            for turn in recommendations
        )
    if invariant == "never_invent_product_facts":
        recommendations = [
            turn for turn in turns if (turn.get("decision_result") or {}).get("ranked_candidates")
        ]
        if not recommendations:
            return None
        return all(
            {
                (item.get("sku_id"), item.get("price"))
                for item in turn.get("presentation", {}).get("products", [])
            }.issubset(
                {
                    (item.get("sku_id"), item.get("price"))
                    for item in turn["decision_result"]["ranked_candidates"]
                }
            )
            for turn in recommendations
        )
    if invariant == "never_present_unknown_service_as_known":
        unknown = [
            turn for turn in turns
            if turn.get("intent") == "service_question"
            and (turn.get("grounding_data") or {}).get("verified") is False
        ]
        if not unknown:
            return None
        return all(
            "not available" not in (turn.get("response_text") or "").casefold()
            for turn in unknown
        )
    if invariant == "never_invent_review_evidence":
        unknown = [
            turn for turn in turns
            if (turn.get("grounding_data") or {}).get("unknown_topics")
        ]
        if not unknown:
            return None
        return all(
            "don't have enough review information" in (turn.get("response_text") or "").casefold()
            for turn in unknown
        )
    if invariant == "never_treat_missing_evidence_as_false":
        relevant = [
            turn for turn in turns
            if (turn.get("grounding_data") or {}).get("verified") is False
            or (turn.get("grounding_data") or {}).get("unknown_topics")
        ]
        if not relevant:
            return None
        return all(
            "not available" not in (turn.get("response_text") or "").casefold()
            for turn in relevant
        )
    criterion_prefixes = {
        "never_present_unknown_service_as_known": ("grounding.valid", "grounding.reason.unknown_service"),
        "never_treat_missing_evidence_as_false": ("grounding.valid", "grounding.reason."),
        "never_invent_product_facts": ("grounding.valid", "grounding.reason."),
        "never_invent_review_evidence": ("grounding.valid", "grounding.reason."),
    }
    patterns = criterion_prefixes.get(invariant)
    if patterns:
        checks = [
            check
            for check in result.checks
            if any(pattern in check["criterion"] for pattern in patterns)
        ]
        return all(check["passed"] for check in checks) if checks else None
    return None


def _usage_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _usage_totals(calls: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {
        "api_calls": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "approximate_cost_usd": 0.0,
        "unknown_price_calls": 0,
    }
    by_model: Dict[str, Dict[str, Any]] = {}
    for call in calls:
        model = call.get("model") or "unknown"
        usage = _usage_dict(call.get("usage"))
        input_tokens = int(usage.get("input_tokens") or 0)
        details = _usage_dict(usage.get("input_tokens_details"))
        cached = int(details.get("cached_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
        model_totals = by_model.setdefault(
            model,
            {
                "api_calls": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "approximate_cost_usd": 0.0,
            },
        )
        for target in (totals, model_totals):
            target["api_calls"] += 1
            target["input_tokens"] += input_tokens
            target["cached_input_tokens"] += cached
            target["output_tokens"] += output_tokens
            target["total_tokens"] += total_tokens
        rates = API_PRICING_PER_MILLION.get(model)
        if rates:
            cost = (
                max(0, input_tokens - cached) * rates["input"]
                + cached * rates["cached_input"]
                + output_tokens * rates["output"]
            ) / 1_000_000
            totals["approximate_cost_usd"] += cost
            model_totals["approximate_cost_usd"] += cost
        else:
            totals["unknown_price_calls"] += 1
    totals["approximate_cost_usd"] = round(totals["approximate_cost_usd"], 6)
    for item in by_model.values():
        item["approximate_cost_usd"] = round(item["approximate_cost_usd"], 6)
    totals["by_model"] = by_model
    totals["pricing_source"] = PRICING_SOURCE
    return totals


def _mean(values: Iterable[Any]) -> Optional[float]:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numbers) / len(numbers), 3) if numbers else None


def _call_stage(call: Dict[str, Any]) -> str:
    try:
        payload = json.loads(call.get("raw_model_output") or "")
    except (TypeError, json.JSONDecodeError):
        return "conversational_generation"
    if isinstance(payload, dict) and "selection_mode" in payload:
        return "shopping_selection"
    if isinstance(payload, dict) and "intent" in payload:
        return "extraction"
    return "conversational_generation"


def _performance_summary(
    result_dicts: Iterable[Dict[str, Any]],
    production_calls: List[Dict[str, Any]],
    judge_results: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    turns = [
        turn
        for result in result_dicts
        for turn in actual_turns(result.get("actual") or {})
    ]
    metrics = [
        (turn.get("timing") or {}).get("metrics_ms") or {} for turn in turns
    ]
    stage_elapsed = {
        stage: [
            call.get("elapsed_ms")
            for call in production_calls
            if _call_stage(call) == stage
        ]
        for stage in ("extraction", "shopping_selection", "conversational_generation")
    }
    judge_calls = [
        {
            "model": item.get("configuration", {}).get("model"),
            "usage": item.get("usage"),
            "elapsed_ms": item.get("elapsed_ms"),
        }
        for item in judge_results
    ]
    response_paths = Counter(
        (turn.get("generation_audit") or {}).get("fallback_used") is True
        for turn in turns
    )
    usage = _usage_totals([*production_calls, *judge_calls])
    return {
        "turns_measured": len(turns),
        "latency_ms_average": {
            "extraction": _mean(item.get("extraction_latency") for item in metrics),
            "shopping_selection": _mean(stage_elapsed["shopping_selection"]),
            "conversational_generation": _mean(item.get("generation_latency") for item in metrics),
            "generation_ttft": _mean(item.get("generation_ttft") for item in metrics),
            "total_turn": _mean(item.get("total_turn_latency") for item in metrics),
            "cx_judge": _mean(item.get("elapsed_ms") for item in judge_results),
        },
        "response_paths": {
            "generated": response_paths.get(False, 0),
            "deterministic_fallback": response_paths.get(True, 0),
        },
        "usage_and_cost": usage,
    }


def _integrity_summary(items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    results = list(items)
    issue_keys = (
        "non_negotiable_issues",
        "grounding_or_factual_issues",
        "recommendation_authority_issues",
        "state_integrity_issues",
    )
    return {
        "overall_status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
        "cases_assessed": len(results),
        "cases_passed": sum(item["status"] == "PASS" for item in results),
        **{key: [issue for item in results for issue in item[key]] for key in issue_keys},
    }


def _full_live_report_appendix(run: Dict[str, Any]) -> str:
    integrity = run.get("system_integrity_summary")
    cx = run.get("shopping_experience_summary")
    performance = run.get("performance_and_cost")
    if not integrity or not cx or not performance:
        return ""
    lines = [
        "",
        "## Independent System Integrity",
        "",
        f"Overall: **{integrity['overall_status']}** — {integrity['cases_passed']}/{integrity['cases_assessed']} assessed cases passed.",
        "",
    ]
    for key, label in (
        ("non_negotiable_issues", "Non-negotiable failures"),
        ("grounding_or_factual_issues", "Grounding or factual violations"),
        ("recommendation_authority_issues", "Recommendation-authority violations"),
        ("state_integrity_issues", "State-integrity failures"),
    ):
        issues = integrity[key]
        lines.append(f"- {label}: {len(issues)}")
    lines.extend(
        [
            "",
            "## Independent Shopping Experience",
            "",
            f"Judged cases: {cx['judged_cases']}; overall average: **{cx['overall_average']:.2f}/3**",
            "",
            "| Criterion | Cases | Average |",
            "|---|---:|---:|",
        ]
    )
    for name in CX_CRITERIA:
        item = cx["criteria"][name]
        average = "N/A" if item["average"] is None else f"{item['average']:.2f}"
        lines.append(f"| {name.replace('_', ' ').title()} | {item['scored_cases']} | {average} |")
    scores = [
        (item["case_id"], item["shopping_experience"]["judgment"]["overall_score"])
        for item in run["results"]
        if item.get("shopping_experience")
    ]
    lines.extend(["", "Case distribution:"])
    distribution = Counter(score for _, score in scores)
    lines.extend(f"- {score}/3: {distribution.get(score, 0)} cases" for score in range(4))
    lines.extend(["", "## Performance and cost", ""])
    latency = performance["latency_ms_average"]
    for key, value in latency.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {'N/A' if value is None else f'{value:.2f} ms'}")
    usage = performance["usage_and_cost"]
    lines.extend(
        [
            f"- API calls: {usage['api_calls']}",
            f"- Tokens: {usage['total_tokens']} total ({usage['input_tokens']} input, {usage['cached_input_tokens']} cached input, {usage['output_tokens']} output)",
            f"- Approximate API cost: ${usage['approximate_cost_usd']:.4f}",
            f"- Generated responses / deterministic fallbacks: {performance['response_paths']['generated']} / {performance['response_paths']['deterministic_fallback']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    global SUITE_VERSION, SUITE_DIR, DEFAULT_OUTPUT_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-version", choices=("v1", "v2"), default="v2")
    parser.add_argument("--category")
    parser.add_argument("--case", dest="case_id")
    parser.add_argument("--deterministic-only", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--cx-judge",
        action="store_true",
        help="Run the independent Sol Shopping Experience judge for live customer journeys.",
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--score-file", default=str(SUITE_DIR / "manual_scores.json"))
    args = parser.parse_args()
    SUITE_VERSION = args.suite_version
    SUITE_DIR = ROOT / "evals" / SUITE_ID / SUITE_VERSION
    DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "evals" / SUITE_ID / SUITE_VERSION
    if args.output_dir == str(ROOT / "artifacts" / "evals" / SUITE_ID / "v2"):
        args.output_dir = str(DEFAULT_OUTPUT_DIR)
    if args.score_file == str(ROOT / "evals" / SUITE_ID / "v2" / "manual_scores.json"):
        args.score_file = str(SUITE_DIR / "manual_scores.json")
    if args.live and args.deterministic_only:
        parser.error("choose either --live or --deterministic-only")
    if args.cx_judge and not args.live:
        parser.error("--cx-judge requires --live")

    documents = load_documents()
    validation = validate_documents(documents)
    if not validation["valid"]:
        for error in validation["errors"]:
            print(f"SCHEMA ERROR: {error}")
        return 2
    print(f"Validated {validation['case_count']} cases against eval schema {SCHEMA_VERSION}.")
    if args.validate_only:
        return 0

    live_client: Optional[RecordingClient] = None
    judge_client: Optional[Any] = None
    if args.live:
        load_dotenv(ROOT / ".env")
        if not os.getenv("OPENAI_API_KEY"):
            print("OPENAI_API_KEY is required for --live.", file=sys.stderr)
            return 2
        from openai import OpenAI
        live_client = RecordingClient(OpenAI(api_key=os.environ["OPENAI_API_KEY"]))
        if args.cx_judge:
            judge_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    selected = []
    for document in documents:
        for case in document["cases"]:
            if args.category and case["category"] != args.category:
                continue
            if args.case_id and case["case_id"] != args.case_id:
                continue
            if not args.live and case.get("live_only"):
                continue
            selected.append((document, case))
    if not selected:
        print("No cases matched the requested filters.", file=sys.stderr)
        return 2

    started = datetime.now(timezone.utc)
    manual_scores = load_manual_scores(Path(args.score_file))
    results = []
    for document, case in selected:
        call_start = len(live_client.calls) if live_client else 0
        result = evaluate_case(case, document["suite"], live_client)
        if live_client:
            result.actual["model_calls"] = deepcopy(live_client.calls[call_start:])
        if result.qualitative_pending and case["case_id"] in manual_scores:
            score = manual_scores[case["case_id"]]
            result.actual["manual_score"] = score["score"]
            result.actual["manual_rationale"] = score["rationale"]
            result.qualitative_pending = False
        results.append(result)
    invariant_outcomes = {name: True for name in sorted(INVARIANTS)}
    for (_, case), result in zip(selected, results):
        for invariant in case.get("invariants", []):
            outcome = direct_invariant_outcome(invariant, result)
            if outcome is not None:
                invariant_outcomes[invariant] = invariant_outcomes[invariant] and outcome
    result_dicts = [result.as_dict() for result in results]
    integrity_results = []
    cx_results = []
    for (document, case), result, result_dict in zip(selected, results, result_dicts):
        case_invariants = {
            name: outcome
            for name in case.get("invariants", [])
            for outcome in [direct_invariant_outcome(name, result)]
            if outcome is not None
        }
        integrity = evaluate_system_integrity(
            case, result.actual, invariant_outcomes=case_invariants
        )
        integrity_results.append(integrity)
        result_dict["system_integrity"] = integrity
        if judge_client is not None and result.actual.get("turns"):
            payload = build_cx_judge_payload(case, result.actual)
            if payload["journey"]:
                judgment = judge_shopping_experience(judge_client, payload)
                result_dict["shopping_experience_input"] = payload
                result_dict["shopping_experience"] = judgment
                cx_results.append(judgment)

    run = {
        "run_id": started.strftime("%Y-%m-%d_%H%M%S"),
        "created_at": started.isoformat(),
        "suite_id": SUITE_ID,
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "mode": "live" if args.live else "deterministic",
        "schema_version": SCHEMA_VERSION,
        "configuration": {
            "models": {task.value: {"model": DEFAULT_MODELS[task], "reasoning_effort": DEFAULT_REASONING[task]} for task in DEFAULT_MODELS},
            "prompt_hashes": prompt_hashes(),
            "fixture_version": f"{CATALOG_FIXTURE_VERSION}+{REVIEW_FIXTURE_VERSION}",
            "code_commit": code_commit(),
            "scoring_configuration": {
                "schema_version": SCHEMA_VERSION,
                "severity_levels": ["critical", "major", "minor"],
                "manual_rubric": "0-3",
            },
            "cx_judge": cx_judge_configuration() if args.cx_judge else None,
        },
        "filters": {"category": args.category, "case_id": args.case_id},
        "summary": summary(results),
        "critical_invariants": invariant_outcomes,
        "model_calls": live_client.calls if live_client else [],
        "system_integrity_summary": _integrity_summary(integrity_results),
        "shopping_experience_summary": cx_summary(cx_results) if cx_results else None,
        "results": result_dicts,
    }
    run["performance_and_cost"] = _performance_summary(
        result_dicts,
        live_client.calls if live_client else [],
        cx_results,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / f"{run['run_id']}_run.json"
    report_path = output_dir / f"{run['run_id']}_report.md"
    if raw_path.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation run {run['run_id']}")
    raw_path.write_text(json.dumps(run, indent=2, default=str) + "\n", encoding="utf-8")
    report = markdown_report(run) + _full_live_report_appendix(run)
    report_path.write_text(report, encoding="utf-8")
    write_eval_index()
    print(report)
    print(f"Raw results: {os.path.relpath(raw_path, ROOT)}")
    print(f"Report: {os.path.relpath(report_path, ROOT)}")
    return 1 if run["summary"]["failed"] or not all(invariant_outcomes.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
