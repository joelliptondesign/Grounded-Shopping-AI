import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from evals.cx_judge import (
    CX_CRITERIA,
    build_cx_judge_payload,
    cx_judge_configuration,
    judge_shopping_experience,
    validate_cx_judgment,
)
from evals.shopping_experience_calibration import selected_cases
from evals.system_integrity import evaluate_system_integrity


def judgment_fixture():
    result = {
        name: {"applicable": True, "score": 2, "rationale": f"Observed {name}."}
        for name in CX_CRITERIA
    }
    result["alternative_usefulness"] = {
        "applicable": False,
        "score": None,
        "rationale": "No near-match situation occurred.",
    }
    result.update(
        {
            "overall_score": 2,
            "overall_rationale": "Competent shopping assistance.",
            "biggest_customer_experience_issue": "Could provide more decision support.",
        }
    )
    return result


class FakeResponses:
    def __init__(self, output):
        self.output = output
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            output_text=json.dumps(self.output),
            usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 10}),
        )


class TwoJudgeEvaluationTests(unittest.TestCase):
    def test_calibration_is_exactly_five_named_existing_v2_cases(self):
        cases = selected_cases()
        self.assertEqual(len(cases), 5)
        self.assertEqual(len({case["case_id"] for _, case, _ in cases}), 5)
        latex = next(case for _, case, _ in cases if case["case_id"] == "v2_allergy_unknown_safe_001")
        self.assertEqual(latex["kind"], "understanding")
        self.assertTrue(latex["turns"][0]["fixture_update"]["hard_constraints"]["exclude_latex"])

    def test_judge_defaults_to_strong_offline_model_without_changing_production(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(cx_judge_configuration()["model"], "gpt-5.6-sol")
            self.assertEqual(cx_judge_configuration()["reasoning_effort"], "high")

    def test_na_criterion_must_have_null_score(self):
        judgment = judgment_fixture()
        validate_cx_judgment(judgment)
        judgment["alternative_usefulness"]["score"] = 0
        with self.assertRaises(ValueError):
            validate_cx_judgment(judgment)

    def test_structured_judge_request_and_raw_output_are_preserved(self):
        responses = FakeResponses(judgment_fixture())
        result = judge_shopping_experience(
            SimpleNamespace(responses=responses),
            {"case_id": "case", "journey": [], "shopping_experience_rubric": {}},
            instruction="Judge shopping experience.",
        )
        self.assertEqual(responses.request["model"], "gpt-5.6-sol")
        self.assertTrue(responses.request["text"]["format"]["strict"])
        self.assertEqual(result["judgment"]["overall_score"], 2)
        self.assertEqual(result["human_calibration_status"], "pending")
        self.assertIn("overall_rationale", result["raw_model_output"])

    def test_judge_payload_contains_customer_context_not_generation_audit(self):
        case = {
            "case_id": "case",
            "qualitative": {"criteria": ["tone"]},
            "turns": [{"user": "Help", "expected": {}}],
        }
        actual = {
            "turns": [
                {
                    "user": "Help",
                    "final_shopper_response": "Here are two options.",
                    "parsed_state": {"soft_preferences": {"budget_target": 1000}},
                    "decision_result": {"decision": "ALLOW"},
                    "grounding_evidence": {"decision": "ALLOW"},
                    "presentation_contract": {"modality": "recommendation_cards"},
                    "generation_audit": {"attempts": [{"valid": True}]},
                }
            ]
        }
        payload = build_cx_judge_payload(case, actual)
        serialized = json.dumps(payload)
        self.assertIn("Here are two options.", serialized)
        self.assertIn("budget_target", serialized)
        self.assertNotIn("generation_audit", serialized)

    def test_integrity_fails_latex_violating_authoritative_selection(self):
        case = {
            "turns": [
                {
                    "expected": {
                        "state": {"hard_constraints": {"exclude_latex": True}}
                    }
                }
            ]
        }
        actual = {
            "turns": [
                {
                    "parsed_state": {"hard_constraints": {"exclude_latex": True}},
                    "decision_result": {
                        "selected_sku": {
                            "sku_id": "LATEX",
                            "contains_latex": True,
                            "available_sizes": ["king"],
                        }
                    },
                    "presentation_contract": {"products": [{"sku_id": "LATEX"}]},
                }
            ]
        }
        result = evaluate_system_integrity(case, actual)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["non_negotiable_issues"])


if __name__ == "__main__":
    unittest.main()
