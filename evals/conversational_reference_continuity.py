#!/usr/bin/env python3
"""Run the focused live conversational-reference continuity regression."""

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response
from engine.data import SKU_CATALOG
from engine.model_config import DEFAULT_MODELS, DEFAULT_REASONING
from engine.preference_extraction import new_preference_state
from evals.cx_judge import (
    build_cx_judge_payload,
    cx_judge_configuration,
    cx_summary,
    judge_shopping_experience,
)
from evals.runner import (
    RecordingClient,
    _integrity_summary,
    _performance_summary,
    code_commit,
    prompt_hashes,
    write_eval_index,
)
from evals.system_integrity import evaluate_system_integrity


SUITE_ID = "conversational-reference-continuity"
SUITE_NAME = "Conversational Reference Continuity"
SUITE_VERSION = "v1"
DEFINITION = ROOT / "evals" / SUITE_ID / SUITE_VERSION / "journeys.json"
OUTPUT_DIR = ROOT / "artifacts" / "evals" / SUITE_ID / SUITE_VERSION
CX_FOCUS = """

For this focused regression, emphasize context continuity, natural understanding,
shopper effort, clarification restraint, forward momentum, and conversational
autonomy. The central question is: would a normal customer feel like the shopping
agent remembered what they were talking about? Do not reward technical caution
over obvious contextual understanding.
"""


def load_definition() -> Dict[str, Any]:
    document = json.loads(DEFINITION.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "suite_id",
        "suite_name",
        "suite_version",
        "journeys",
    }
    if required - set(document):
        raise ValueError("Focused reference definition is incomplete")
    if document["suite_id"] != SUITE_ID or document["suite_version"] != SUITE_VERSION:
        raise ValueError("Focused reference definition identity is invalid")
    if not 5 <= len(document["journeys"]) <= 7:
        raise ValueError("Focused reference regression must contain 5-7 journeys")
    return document


def visible_presentation(presentation: Dict[str, Any]) -> str:
    modality = presentation.get("modality", "conversation")
    products = presentation.get("products") or []
    if modality == "recommendation_cards":
        items = "; ".join(
            f"{index}. {item.get('name')} ({item.get('sku_id')})"
            for index, item in enumerate(products, start=1)
        )
        return f"[{modality}: {items}]"
    if modality == "comparison_table":
        items = " vs ".join(item.get("name", "") for item in products)
        return f"[{modality}: {items}]"
    if modality == "product_detail" and products:
        return f"[{modality}: {products[0].get('name')} ({products[0].get('sku_id')})]"
    return f"[{modality}]"


def latest_with_modality(state: Dict[str, Any], modality: str) -> Dict[str, Any]:
    for item in reversed(state.get("recent_presentations", [])):
        if item.get("modality") == modality:
            return item
    return {}


def assess_reference(
    journey: Dict[str, Any], turns: List[Dict[str, Any]]
) -> Dict[str, Any]:
    focus_index = journey["focus_turn"] - 1
    focus = turns[focus_index]
    before = focus["input_state"]
    turn = focus["turn"]
    action = turn.get("shopping_action") or {}
    action_ids = action.get("product_ids") or []
    expectation = journey["expectation"]
    checks: Dict[str, bool] = {}
    expected_ids: List[str] = []

    if expectation == "compare_recent_cards":
        expected_ids = latest_with_modality(before, "recommendation_cards").get("product_ids", [])[:2]
        checks = {
            "structured_action": action.get("action") == "compare_products",
            "reference_identity": action_ids == expected_ids,
            "direct_progress": turn.get("modality") == "comparison_table",
        }
    elif expectation == "pick_recent_comparison":
        expected_ids = latest_with_modality(before, "comparison_table").get("product_ids", [])
        primary = (turn.get("shopping_selection") or {}).get("primary_product_id")
        candidates = {
            item.get("sku_id") for item in (turn.get("decision_result") or {}).get("ranked_candidates", [])
        }
        checks = {
            "structured_action": action.get("action") == "choose_from_products",
            "reference_identity": action_ids == expected_ids,
            "choice_set_scoped": candidates == set(expected_ids),
            "selected_inside_choice_set": primary in expected_ids,
            "shopper_state_preserved": before.get("hard_constraints") == turn["preference_state"].get("hard_constraints")
            and before.get("priorities") == turn["preference_state"].get("priorities"),
        }
    elif expectation == "attribute_recent_comparison":
        expected_ids = latest_with_modality(before, "comparison_table").get("product_ids", [])
        grounded_ids = [item.get("sku_id") for item in (turn.get("grounding_data") or {}).get("products", [])]
        checks = {
            "structured_action": action.get("action") == "compare_products",
            "reference_identity": action_ids == expected_ids,
            "attribute_grounded_to_comparison": grounded_ids == expected_ids,
        }
        ordinal = turns[journey["ordinal_turn"] - 1]["turn"]
        ordinal_expected = latest_with_modality(
            turns[journey["ordinal_turn"] - 1]["input_state"], "comparison_table"
        ).get("product_ids", [])
        checks["second_one_resolved"] = bool(ordinal_expected) and (
            (ordinal.get("shopping_action") or {}).get("product_ids") == ordinal_expected[1:2]
        )
    elif expectation == "review_pronoun":
        prior_ids = before.get("recent_presentations", [])[-1].get("product_ids", [])
        expected_ids = prior_ids[:1]
        checks = {
            "reference_identity": action_ids == expected_ids,
            "review_topic_preserved": (turn.get("turn_context") or {}).get("information_source") == "reviews"
            and (turn.get("turn_context") or {}).get("review_topic") == "cooling",
            "grounded_review_response": turn.get("response_strategy") == "review_evidence_lookup",
        }
    elif expectation == "service_switch":
        expected_ids = ["S06"]
        product = (turn.get("grounding_data") or {}).get("product") or {}
        checks = {
            "reference_identity": action_ids == expected_ids,
            "service_topic_preserved": action.get("service_attribute") == "haul_away",
            "service_grounded_to_new_product": product.get("sku_id") == "S06",
        }
    elif expectation == "natural_clarification":
        response = focus["final_shopper_response"]
        checks = {
            "clarification_requested": turn.get("response_strategy") == "clarification",
            "natural_language": not any(
                phrase in response.casefold()
                for phrase in ("reference resolution", "product id", "please specify the product")
            ),
            "state_preserved": before.get("hard_constraints") == turn["preference_state"].get("hard_constraints"),
        }

    clarification = turn.get("response_strategy") == "clarification"
    if expectation != "natural_clarification":
        checks["no_unnecessary_clarification"] = not clarification
    audit = focus.get("generation_audit") or {}
    checks["response_grounded"] = bool(audit.get("fallback_used")) or bool(
        (audit.get("attempts") or [{}])[-1].get("valid")
    )
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "expected_product_ids": expected_ids,
        "resolved_product_ids": action_ids,
        "clarification": clarification,
        "selected_product_id": (turn.get("shopping_selection") or {}).get("primary_product_id"),
    }


def run_journey(client: RecordingClient, definition: Dict[str, Any]) -> Dict[str, Any]:
    state = new_preference_state()
    previous = None
    history: List[Dict[str, str]] = []
    turns: List[Dict[str, Any]] = []
    for user_message in definition["turns"]:
        input_state = deepcopy(state)
        turn = process_conversation_turn(
            user_message,
            state,
            SKU_CATALOG,
            client=client,
            previous_decision_result=previous,
            conversation_history=history,
        )
        audit: Dict[str, Any] = {}
        response = generate_turn_response(
            turn,
            user_message,
            history,
            catalog=SKU_CATALOG,
            client=client,
            audit=audit,
        )
        visible = f"{visible_presentation(turn['presentation'])} {response}"
        turns.append(
            {
                "user": user_message,
                "input_state": input_state,
                "parsed_state": deepcopy(turn["preference_state"]),
                "decision_preferences": turn.get("decision_preferences"),
                "decision_result": turn.get("decision_result"),
                "shopping_selection": turn.get("shopping_selection"),
                "grounding_evidence": turn.get("grounding_evidence") or turn.get("grounding_data"),
                "presentation_contract": turn.get("presentation"),
                "final_shopper_response": response,
                "customer_visible_assistant": visible,
                "generation_audit": audit,
                "timing": turn.get("timing"),
                "turn": turn,
            }
        )
        history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response},
            ]
        )
        state = turn["preference_state"]
        if turn.get("decision_result"):
            previous = turn["decision_result"]
    actual = {"turns": turns}
    semantic = assess_reference(definition, turns)
    integrity = evaluate_system_integrity(
        {"case_id": definition["case_id"], "turns": []}, actual
    )
    return {
        "case_id": definition["case_id"],
        "label": definition["label"],
        "definition": definition,
        "actual": actual,
        "semantic_reference": semantic,
        "system_integrity": integrity,
    }


def report_markdown(run: Dict[str, Any]) -> str:
    lines = [
        "# Conversational Reference Continuity v1",
        "",
        f"Run: `{run['run_id']}`  ",
        f"Mode: `{run['mode']}`  ",
        f"System Integrity: **{run['system_integrity_summary']['overall_status']}**  ",
        f"Core reference cases: **{run['summary']['passed']}/{run['summary']['cases_run']} passed**  ",
        f"Shopping Experience average: **{run['shopping_experience_summary']['overall_average']:.2f}/3**",
        "",
        "## Focused results",
        "",
        "| Journey | Integrity | CX | Clarification? | Reference resolved? |",
        "|---|---|---:|---|---|",
    ]
    for result in run["results"]:
        semantic = result["semantic_reference"]
        cx = result["shopping_experience"]["judgment"]["overall_score"]
        lines.append(
            f"| {result['label']} | {result['system_integrity']['status']} | {cx}/3 | "
            f"{'Yes' if semantic['clarification'] else 'No'} | {'Yes' if semantic['passed'] else 'No'} |"
        )

    pick = next(item for item in run["results"] if item["case_id"] == "comparison_pick_one")
    pick_turns = pick["actual"]["turns"]
    shown = latest_with_modality(pick_turns[1]["input_state"], "recommendation_cards")
    compared = latest_with_modality(pick_turns[2]["input_state"], "comparison_table")
    pick_semantic = pick["semantic_reference"]
    names = {item["sku_id"]: item["name"] for item in SKU_CATALOG}
    lines.extend(
        [
            "",
            "## Compare → pick evidence",
            "",
            f"- Products shown: {', '.join(names.get(item, item) for item in shown.get('product_ids', []))}",
            f"- Products compared: {', '.join(names.get(item, item) for item in compared.get('product_ids', []))}",
            f"- Shopper follow-up: {pick_turns[2]['user']}",
            f"- Resolved choice set: {', '.join(pick_semantic['resolved_product_ids'])}",
            f"- Selected product: {names.get(pick_semantic['selected_product_id'], pick_semantic['selected_product_id'])}",
            f"- Unnecessary clarification: {'Yes' if pick_semantic['clarification'] else 'No'}",
            f"- Grounding result: {'PASS' if pick_semantic['checks'].get('response_grounded') else 'FAIL'}",
            "",
            "## Exact chronological customer-facing conversations",
        ]
    )
    for result in run["results"]:
        lines.extend(["", f"### {result['label']}", ""])
        for turn in result["actual"]["turns"]:
            lines.append(f"**Shopper:** {turn['user']}")
            lines.append("")
            lines.append(f"**Assistant:** {turn['customer_visible_assistant']}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    document = load_definition()
    print(f"Validated {len(document['journeys'])} focused journeys.")
    if args.validate_only:
        return 0
    if not args.live:
        parser.error("the focused regression is live-only; pass --live")

    load_dotenv(ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for --live.", file=sys.stderr)
        return 2
    from openai import OpenAI

    production = RecordingClient(OpenAI(api_key=os.environ["OPENAI_API_KEY"]))
    judge_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    judge_instruction = (
        ROOT / "prompts" / "shopping_experience_judge.md"
    ).read_text(encoding="utf-8") + CX_FOCUS
    started = datetime.now(timezone.utc)
    results = []
    judge_results = []
    for journey in document["journeys"]:
        result = run_journey(production, journey)
        judge_case = {
            "case_id": journey["case_id"],
            "turns": [{"qualitative": {"reference_continuity": journey["expectation"]}}],
        }
        payload = build_cx_judge_payload(judge_case, result["actual"])
        judgment = judge_shopping_experience(
            judge_client, payload, instruction=judge_instruction
        )
        result["shopping_experience_input"] = payload
        result["shopping_experience"] = judgment
        judge_results.append(judgment)
        results.append(result)

    integrity_results = [item["system_integrity"] for item in results]
    passed = sum(item["semantic_reference"]["passed"] for item in results)
    run = {
        "run_id": started.strftime("%Y-%m-%d_%H%M%S"),
        "created_at": started.isoformat(),
        "suite_id": SUITE_ID,
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "mode": "live",
        "schema_version": document["schema_version"],
        "configuration": {
            "models": {
                task.value: {
                    "model": DEFAULT_MODELS[task],
                    "reasoning_effort": DEFAULT_REASONING[task],
                }
                for task in DEFAULT_MODELS
            },
            "cx_judge": cx_judge_configuration(),
            "prompt_hashes": prompt_hashes(),
            "code_commit": code_commit(),
        },
        "summary": {
            "cases_run": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        "system_integrity_summary": _integrity_summary(integrity_results),
        "shopping_experience_summary": cx_summary(judge_results),
        "model_calls": production.calls,
        "results": results,
    }
    run["performance_and_cost"] = _performance_summary(
        [{"actual": item["actual"]} for item in results],
        production.calls,
        judge_results,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / f"{run['run_id']}_run.json"
    report_path = OUTPUT_DIR / f"{run['run_id']}_report.md"
    if raw_path.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to overwrite {run['run_id']}")
    raw_path.write_text(json.dumps(run, indent=2, default=str) + "\n", encoding="utf-8")
    report_path.write_text(report_markdown(run), encoding="utf-8")
    write_eval_index()
    print(report_markdown(run))
    print(f"Raw results: {raw_path.relative_to(ROOT)}")
    print(f"Report: {report_path.relative_to(ROOT)}")
    integrity_passed = run["system_integrity_summary"]["overall_status"] == "PASS"
    return 0 if passed == len(results) and integrity_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
