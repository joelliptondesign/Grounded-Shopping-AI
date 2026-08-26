#!/usr/bin/env python3
"""Run the fixed five-case live CX calibration without running the full v2 suite."""

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.cx_judge import (
    CX_CRITERIA,
    build_cx_judge_payload,
    cx_judge_configuration,
    cx_summary,
    judge_shopping_experience,
)
from evals.runner import (
    RecordingClient,
    direct_invariant_outcome,
    evaluate_case,
    load_documents,
    prompt_hashes,
    validate_documents,
    write_eval_index,
)
from evals.system_integrity import actual_turns, evaluate_system_integrity
from engine.model_config import DEFAULT_MODELS, DEFAULT_REASONING


CONCEPT_ID = "shopping-experience-calibration"
CONCEPT_NAME = "Shopping Experience Calibration"
CONCEPT_VERSION = "v1"
OUTPUT_DIR = ROOT / "artifacts" / "evals" / CONCEPT_ID / CONCEPT_VERSION
PILOT_CASES: Tuple[Tuple[str, str], ...] = (
    ("v2_flexible_budget_range_001", "Flexible budget / autonomy"),
    ("v2_near_match_tradeoffs_001", "No exact match / alternatives"),
    ("v2_allergy_unknown_safe_001", "Latex safety boundary"),
    ("v2_pronoun_and_topic_continuity_001", "Conversational context"),
    ("v2_fuzzy_complaint_001", "Fuzzy preference discovery"),
)


def selected_cases() -> List[Tuple[Dict[str, Any], Dict[str, Any], str]]:
    documents = load_documents()
    validation = validate_documents(documents)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    by_id = {
        case["case_id"]: (document, case)
        for document in documents
        for case in document["cases"]
    }
    selected = []
    for case_id, label in PILOT_CASES:
        if case_id not in by_id:
            raise ValueError(f"Missing calibration case {case_id}")
        document, case = by_id[case_id]
        if case_id == "v2_allergy_unknown_safe_001":
            case = deepcopy(case)
            case["kind"] = "understanding"
            case["dimensions"] = [
                "understanding",
                "decision_correctness",
                "grounding",
                "conversation_quality",
            ]
            case["invariants"] = [
                "never_recommend_ineligible_product",
                "never_silently_relax_hard_requirement",
                "never_invent_product_facts",
                "never_treat_missing_evidence_as_false",
            ]
            case.pop("preferences", None)
            case.pop("expected", None)
            case["turns"] = [
                {
                    "user": "I'm looking for a king around $1,200, and I'm allergic to latex.",
                    "fixture_update": {
                        "hard_constraints": {"size": "king", "exclude_latex": True},
                        "soft_preferences": {"budget_target": 1200},
                    },
                    "expected": {
                        "intent": "recommend",
                        "state": {
                            "hard_constraints": {"size": "king", "exclude_latex": True},
                            "soft_preferences": {"budget_target": 1200},
                        },
                        "decision": "ALLOW",
                        "winner": "SAFE",
                        "modality": "recommendation_cards",
                    },
                }
            ]
            case["qualitative"] = {
                "criteria": [
                    "natural_understanding",
                    "forward_momentum",
                    "customer_language",
                    "tone",
                    "decision_support",
                ]
            }
        selected.append((document, case, label))
    if len(selected) != 5:
        raise AssertionError("The calibration must contain exactly five cases")
    return selected


def validate_calibration_definition() -> Dict[str, Any]:
    selected = selected_cases()
    return {
        "valid": len(selected) == 5,
        "case_ids": [case["case_id"] for _, case, _ in selected],
        "production_models": {
            task.value: DEFAULT_MODELS[task] for task in DEFAULT_MODELS
        },
        "cx_judge": cx_judge_configuration(),
    }


def _invariant_results(case: Dict[str, Any], result: Any) -> Dict[str, bool]:
    outcomes = {}
    for invariant in case.get("invariants", []):
        outcome = direct_invariant_outcome(invariant, result)
        if outcome is not None:
            outcomes[invariant] = outcome
    return outcomes


def _render_products(products: List[Dict[str, Any]]) -> List[str]:
    if not products:
        return []
    keys = ["name", "price", "why_it_matches", "tradeoff", "service_indicator"]
    lines = ["", "Structured UI — product cards", ""]
    lines.append("| " + " | ".join(key.replace("_", " ").title() for key in keys) + " |")
    lines.append("|" + "|".join("---" for _ in keys) + "|")
    for product in products:
        values = []
        for key in keys:
            value = product.get(key)
            if key == "price" and isinstance(value, (int, float)):
                value = f"${value:,.0f}"
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            if isinstance(value, dict):
                label = value.get("label", "Service")
                available = value.get("available")
                value = f"{label}: {'Yes' if available is True else 'No' if available is False else 'Unknown'}"
            values.append(str(value if value is not None else "Unknown"))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _render_presentation(presentation: Dict[str, Any]) -> List[str]:
    if not presentation:
        return []
    lines = ["", f"Presentation: `{presentation.get('modality', 'conversation')}`"]
    lines.extend(_render_products(presentation.get("products") or []))
    comparison = presentation.get("comparison") or {}
    if comparison.get("rows"):
        product_names = comparison.get("product_names") or []
        lines.extend(["", "Structured UI — comparison table", ""])
        lines.append("| Attribute | " + " | ".join(product_names) + " |")
        lines.append("|---|" + "|".join("---" for _ in product_names) + "|")
        for row in comparison["rows"]:
            values = row.get("values") or []
            lines.append(
                "| " + str(row.get("label") or row.get("key")) + " | "
                + " | ".join(str(value) for value in values) + " |"
            )
    actions = presentation.get("actions") or []
    if actions:
        lines.extend(["", "Actions:"])
        for action in actions:
            lines.append(f"- `{action.get('action')}` — {action.get('label') or action.get('sku_id')}")
    replies = presentation.get("suggested_replies") or []
    if replies:
        lines.extend(["", "Suggested replies:"])
        for reply in replies:
            lines.append(f"- {reply}")
    return lines


def _conversation_lines(actual: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for index, turn in enumerate(actual_turns(actual), start=1):
        shopper = turn.get("user") or ""
        assistant = turn.get("final_shopper_response") or turn.get("response_text") or ""
        lines.extend(
            [
                f"#### Turn {index} — Shopper",
                "",
                shopper,
                "",
                f"#### Turn {index} — Assistant",
                "",
                assistant,
            ]
        )
        lines.extend(_render_presentation(turn.get("presentation_contract") or turn.get("presentation") or {}))
        lines.append("")
    return lines


def _issues(integrity: Dict[str, Any]) -> List[str]:
    return [
        issue
        for key in (
            "non_negotiable_issues",
            "grounding_or_factual_issues",
            "recommendation_authority_issues",
            "state_integrity_issues",
        )
        for issue in integrity[key]
    ]


def _product_orders(actual: Dict[str, Any]) -> Dict[str, List[str]]:
    turns = actual_turns(actual)
    if not turns:
        return {"deterministic_scorer_order": [], "agent_selected_order": []}
    turn = turns[-1]
    decision = turn.get("decision_result") or {}
    selection = turn.get("shopping_selection") or {}
    presented = (turn.get("presentation_contract") or turn.get("presentation") or {}).get("products", [])
    return {
        "deterministic_scorer_order": [item.get("sku_id") for item in decision.get("ranked_candidates", [])],
        "agent_selected_order": selection.get("selected_product_ids") or [item.get("sku_id") for item in presented],
    }


def _previous_live_run() -> Optional[Dict[str, Any]]:
    paths = sorted(OUTPUT_DIR.glob("*_run.json"), reverse=True)
    for path in paths:
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("mode") == "live":
            run["artifact_path"] = str(path.relative_to(ROOT))
            return run
    return None


def markdown_report(run: Dict[str, Any]) -> str:
    cx = run["shopping_experience_summary"]
    integrity_passed = sum(
        item["system_integrity"]["status"] == "PASS" for item in run["results"]
    )
    lines = [
        "# Shopping Experience Calibration Report",
        "",
        f"- Run: `{run['created_at']}`",
        f"- Cases: {len(run['results'])} (exact fixed calibration slice)",
        f"- Production routing: `{run['configuration']['production_models']}`",
        f"- CX judge: `{run['configuration']['cx_judge']}`",
        f"- System Integrity: {integrity_passed}/{len(run['results'])} passed",
        f"- Shopping Experience average: {cx['overall_average']:.2f}/3",
        "- Human calibration: pending; all human fields are intentionally blank",
        "",
        "The judges are independent. Integrity failures are blocking; CX optimizes the experience inside that boundary. No blended score is produced.",
        "",
        "## Summary",
        "",
        "| Case | Previous CX | New CX | Integrity | Selection changed? | Biggest remaining issue |",
        "|---|---:|---:|---|---|---|",
    ]
    for item in run["results"]:
        judgment = item["shopping_experience"]["judgment"]
        issue = judgment["biggest_customer_experience_issue"].replace("|", "\\|")
        lines.append(
            f"| {item['case_name']} | {item['comparison_to_previous']['previous_cx_score']}/3 | "
            f"{judgment['overall_score']}/3 | {item['system_integrity']['status']} | "
            f"{'Yes' if item['comparison_to_previous']['selection_changed'] else 'No'} | {issue} |"
        )
    lines.extend(["", "## Aggregate Shopping Experience", ""])
    lines.append(f"Overall average: **{cx['overall_average']:.2f}/3**")
    lines.extend(["", "| Criterion | Applicable cases | Average |", "|---|---:|---:|"])
    for name in CX_CRITERIA:
        item = cx["criteria"][name]
        average = "N/A" if item["average"] is None else f"{item['average']:.2f}"
        lines.append(f"| {name.replace('_', ' ').title()} | {item['scored_cases']} | {average} |")

    for item in run["results"]:
        integrity = item["system_integrity"]
        judgment = item["shopping_experience"]["judgment"]
        lines.extend(["", f"## {item['case_name']}", ""])
        comparison = item["comparison_to_previous"]
        lines.extend(
            [
                "### Previous exact transcript",
                "",
                *comparison["previous_transcript_markdown"],
                "",
                "### New exact transcript",
                "",
            ]
        )
        lines.extend(_conversation_lines(item["actual"]))
        lines.extend(
            [
                "### Selection comparison",
                "",
                f"- Previous CX: {comparison['previous_cx_score']}/3",
                f"- New CX: {judgment['overall_score']}/3",
                f"- Product selection changed: {'yes' if comparison['selection_changed'] else 'no'}",
                f"- Deterministic scorer order: `{comparison['new_orders']['deterministic_scorer_order']}`",
                f"- Agent-selected order: `{comparison['new_orders']['agent_selected_order']}`",
                "",
            ]
        )
        lines.extend(["### System Integrity Judge", ""])
        lines.append(f"**{integrity['status']}** — {integrity['rationale']}")
        if integrity["critical_invariants"]:
            lines.extend(["", "Relevant invariants:"])
            for name, passed in integrity["critical_invariants"].items():
                lines.append(f"- {'PASS' if passed else 'FAIL'} — `{name}`")
        findings = _issues(integrity)
        lines.extend(["", "Grounding, factual, non-negotiable, authority, or state issues:"])
        if findings:
            lines.extend(f"- {finding}" for finding in findings)
        else:
            lines.append("- None observed.")

        lines.extend(["", "### Shopping Experience Judge", ""])
        lines.append(f"Overall: **{judgment['overall_score']}/3** — {judgment['overall_rationale']}")
        lines.extend(["", "| Criterion | Score | Rationale |", "|---|---:|---|"])
        for name in CX_CRITERIA:
            criterion = judgment[name]
            score = str(criterion["score"]) if criterion["applicable"] else "N/A"
            rationale = criterion["rationale"].replace("|", "\\|")
            lines.append(f"| {name.replace('_', ' ').title()} | {score} | {rationale} |")
        lines.extend(
            [
                "",
                f"Biggest customer-experience issue: {judgment['biggest_customer_experience_issue']}",
                "",
                "### Human Review",
                "",
                "- Human score:",
                "- Human notes:",
                "- Agreement/disagreement with CX judge:",
            ]
        )
    lines.extend(
        [
            "",
            "## Issues to review before the full Shopping Agent Core v2 evaluation",
            "",
        ]
    )
    for item in run["results"]:
        issue = item["shopping_experience"]["judgment"]["biggest_customer_experience_issue"]
        lines.append(f"- **{item['case_name']}:** {issue}")
    lines.append("")
    return "\n".join(lines)


def run_live() -> Tuple[Path, Path, Dict[str, Any]]:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the live calibration")
    from openai import OpenAI

    previous_run = _previous_live_run()
    if previous_run is None:
        raise RuntimeError("A previous immutable live calibration run is required for comparison")
    previous_by_id = {item["case_id"]: item for item in previous_run["results"]}
    production_client = RecordingClient(OpenAI(api_key=api_key))
    judge_client = OpenAI(api_key=api_key)
    started = datetime.now(timezone.utc)
    results = []
    for document, case, label in selected_cases():
        call_start = len(production_client.calls)
        case_result = evaluate_case(case, document["suite"], production_client)
        case_result.actual["model_calls"] = deepcopy(production_client.calls[call_start:])
        invariants = _invariant_results(case, case_result)
        integrity = evaluate_system_integrity(
            case, case_result.actual, invariant_outcomes=invariants
        )
        judge_payload = build_cx_judge_payload(case, case_result.actual)
        cx_result = judge_shopping_experience(judge_client, judge_payload)
        previous = previous_by_id[case["case_id"]]
        previous_orders = _product_orders(previous["actual"])
        new_orders = _product_orders(case_result.actual)
        results.append(
            {
                "case_id": case["case_id"],
                "case_name": label,
                "source_suite": document["suite"],
                "deterministic_regression_passed": case_result.passed,
                "deterministic_regression_failures": case_result.failures,
                "actual": case_result.actual,
                "system_integrity": integrity,
                "shopping_experience_input": judge_payload,
                "shopping_experience": cx_result,
                "comparison_to_previous": {
                    "previous_run_id": previous_run["run_id"],
                    "previous_cx_score": previous["shopping_experience"]["judgment"]["overall_score"],
                    "previous_assistant_outputs": [
                        turn.get("final_shopper_response") or turn.get("response_text") or ""
                        for turn in actual_turns(previous["actual"])
                    ],
                    "new_assistant_outputs": [
                        turn.get("final_shopper_response") or turn.get("response_text") or ""
                        for turn in actual_turns(case_result.actual)
                    ],
                    "previous_transcript_markdown": _conversation_lines(previous["actual"]),
                    "previous_orders": previous_orders,
                    "new_orders": new_orders,
                    "selection_changed": previous_orders["agent_selected_order"] != new_orders["agent_selected_order"],
                },
                "human_review": {
                    "score": None,
                    "notes": None,
                    "agreement_with_cx_judge": None,
                },
            }
        )
    cx = cx_summary(item["shopping_experience"] for item in results)
    integrity_passed = sum(item["system_integrity"]["status"] == "PASS" for item in results)
    run = {
        "run_id": started.strftime("%Y-%m-%d_%H%M%S"),
        "created_at": started.isoformat(),
        "suite_id": CONCEPT_ID,
        "suite_name": CONCEPT_NAME,
        "suite_version": CONCEPT_VERSION,
        "mode": "live",
        "schema_version": "1.0",
        "configuration": {
            "comparison_baseline": {
                "run_id": previous_run["run_id"],
                "artifact_path": previous_run["artifact_path"],
            },
            "models": {
                task.value: {
                    "model": DEFAULT_MODELS[task],
                    "reasoning_effort": DEFAULT_REASONING[task],
                }
                for task in DEFAULT_MODELS
            },
            "production_models": {
                task.value: {
                    "model": DEFAULT_MODELS[task],
                    "reasoning_effort": DEFAULT_REASONING[task],
                }
                for task in DEFAULT_MODELS
            },
            "cx_judge": cx_judge_configuration(),
            "prompt_hashes": prompt_hashes(),
            "source_suite": "shopping-agent-core/v2",
        },
        "filters": {"fixed_case_ids": [case_id for case_id, _ in PILOT_CASES]},
        "summary": {
            "cases_run": 5,
            "passed": integrity_passed,
            "failed": 5 - integrity_passed,
            "failures_by_severity": {"critical": 5 - integrity_passed, "major": 0, "minor": 0},
        },
        "shopping_experience_summary": cx,
        "results": results,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / f"{run['run_id']}_run.json"
    report_path = OUTPUT_DIR / f"{run['run_id']}_report.md"
    if raw_path.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to overwrite calibration run {run['run_id']}")
    raw_path.write_text(json.dumps(run, indent=2, default=str) + "\n", encoding="utf-8")
    report_path.write_text(markdown_report(run), encoding="utf-8")
    write_eval_index()
    return raw_path, report_path, run


def rerender_existing(path: Path) -> Tuple[Path, Path, Dict[str, Any]]:
    """Create a new immutable presentation artifact without making API calls."""
    source = json.loads(path.read_text(encoding="utf-8"))
    created = datetime.now(timezone.utc)
    run = deepcopy(source)
    run["derived_from_run_id"] = source["run_id"]
    run["live_execution_created_at"] = source["created_at"]
    run["run_id"] = created.strftime("%Y-%m-%d_%H%M%S")
    run["created_at"] = created.isoformat()
    run["mode"] = "live-artifact-rerender"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / f"{run['run_id']}_run.json"
    report_path = OUTPUT_DIR / f"{run['run_id']}_report.md"
    if raw_path.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to overwrite calibration run {run['run_id']}")
    raw_path.write_text(json.dumps(run, indent=2, default=str) + "\n", encoding="utf-8")
    report_path.write_text(markdown_report(run), encoding="utf-8")
    write_eval_index()
    return raw_path, report_path, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--render-run", type=Path)
    args = parser.parse_args()
    validation = validate_calibration_definition()
    print(json.dumps(validation, indent=2))
    if args.validate_only:
        return 0
    if args.render_run:
        raw_path, report_path, _ = rerender_existing(args.render_run)
        print(f"Raw results: {raw_path.relative_to(ROOT)}")
        print(f"Report: {report_path.relative_to(ROOT)}")
        return 0
    if not args.live:
        parser.error("use --live, --validate-only, or --render-run")
    raw_path, report_path, run = run_live()
    print(f"Raw results: {raw_path.relative_to(ROOT)}")
    print(f"Report: {report_path.relative_to(ROOT)}")
    return 1 if run["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
