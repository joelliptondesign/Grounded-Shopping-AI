import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from engine.explanation_llm import get_explanation
from engine.grounding import build_recommendation_evidence, validate_recommendation_text


class CapturingResponses:
    def __init__(self, outputs=None):
        self.request = None
        self.requests = []
        self.outputs = list(outputs or ["Winner is the recommended mattress."])

    def create(self, **kwargs):
        self.request = kwargs
        self.requests.append(kwargs)
        return SimpleNamespace(output_text=self.outputs.pop(0))


class CapturingClient:
    def __init__(self, outputs=None):
        self.responses = CapturingResponses(outputs)


class ExplanationGroundingTests(unittest.TestCase):
    def test_explanation_receives_authoritative_ranked_result(self):
        decision_result = {
            "decision": "ALLOW",
            "selected_sku": {"sku_id": "WINNER", "name": "Winner"},
            "ranked_candidates": [
                {"sku_id": "WINNER", "name": "Winner"},
                {"sku_id": "RUNNER_UP", "name": "Runner Up"},
            ],
            "metadata": {
                "active_normalized_weights": {"cooling": 0.75},
                "candidate_scores": [
                    {
                        "sku_id": "WINNER",
                        "score": 0.9,
                        "previous_rank": 2,
                        "current_rank": 1,
                    }
                ],
            },
        }
        client = CapturingClient(["Winner is the recommended mattress."])
        audit = {}
        with tempfile.NamedTemporaryFile() as log_file:
            with patch("engine.explanation_llm.os.getenv", return_value="test-key"), patch(
                "engine.explanation_llm.OpenAI", return_value=client
            ), patch("engine.explanation_llm.LOG_FILE", log_file.name):
                output = get_explanation(
                    decision_result["selected_sku"],
                    {"user_preferences": {}},
                    decision_result=decision_result,
                    grounding_audit=audit,
                )

        payload = json.loads(client.responses.request["input"][1]["content"])
        self.assertEqual(output, "Winner is the recommended mattress.")
        self.assertNotIn("decision_result", payload)
        self.assertEqual(
            payload["grounding_evidence"]["selected_sku"]["sku_id"], "WINNER"
        )
        self.assertEqual(audit["validation"]["status"], "passed")
        self.assertFalse(audit["fallback"]["used"])

    def test_adversarial_winner_substitution_retries_once_then_falls_back(self):
        decision_result = {
            "decision": "ALLOW",
            "reason": "valid_recommendation",
            "selected_sku": {
                "sku_id": "S06",
                "name": "Metro Cool Comfort",
                "price": 1099,
            },
            "ranked_candidates": [
                {"sku_id": "S06", "name": "Metro Cool Comfort", "price": 1099},
                {"sku_id": "S02", "name": "Polar Motion Elite", "price": 1479},
            ],
            "violations": [],
            "metadata": {"candidate_count": 2, "selected_sku_id": "S06"},
        }
        client = CapturingClient(
            [
                "I recommend Polar Motion Elite as your top match.",
                "Polar Motion Elite is still my recommended choice.",
            ]
        )
        audit = {}
        with tempfile.NamedTemporaryFile() as log_file:
            with patch("engine.explanation_llm.os.getenv", return_value="test-key"), patch(
                "engine.explanation_llm.OpenAI", return_value=client
            ), patch("engine.explanation_llm.LOG_FILE", log_file.name):
                output = get_explanation(
                    decision_result["selected_sku"],
                    {"user_preferences": {"max_price": 1200}},
                    decision_result=decision_result,
                    grounding_audit=audit,
                )

        self.assertEqual(len(client.responses.requests), 2)
        self.assertIn("Metro Cool Comfort", output)
        self.assertNotIn("Polar Motion Elite", output)
        self.assertTrue(audit["retry"]["attempted"])
        self.assertTrue(audit["fallback"]["used"])
        self.assertIn(
            "different_product_recommended:S02",
            audit["validation"]["attempts"][0]["reasons"],
        )

    def test_second_grounded_attempt_is_accepted(self):
        result = {
            "decision": "ALLOW",
            "reason": "valid_recommendation",
            "selected_sku": {"sku_id": "S06", "name": "Metro Cool Comfort"},
            "ranked_candidates": [
                {"sku_id": "S06", "name": "Metro Cool Comfort"},
                {"sku_id": "S02", "name": "Polar Motion Elite"},
            ],
            "violations": [],
            "metadata": {"candidate_count": 2},
        }
        client = CapturingClient(
            [
                "I recommend Polar Motion Elite.",
                "Metro Cool Comfort is the recommended mattress.",
            ]
        )
        audit = {}
        with patch("engine.explanation_llm.os.getenv", return_value="key"), patch(
            "engine.explanation_llm.OpenAI", return_value=client
        ):
            output = get_explanation(
                result["selected_sku"],
                {"user_preferences": {}},
                decision_result=result,
                grounding_audit=audit,
            )
        self.assertEqual(output, "Metro Cool Comfort is the recommended mattress.")
        self.assertEqual(audit["validation"]["status"], "passed")
        self.assertTrue(audit["retry"]["attempted"])
        self.assertFalse(audit["fallback"]["used"])

    def test_unsupported_capability_claims_fail_validation(self):
        result = {
            "decision": "ALLOW",
            "selected_sku": {"sku_id": "S06", "name": "Metro Cool Comfort"},
            "metadata": {},
            "violations": [],
        }
        evidence = build_recommendation_evidence(result, {})
        validation = validate_recommendation_text(
            "I checked live inventory and recommend Metro Cool Comfort based on thousands of customer reviews.",
            evidence,
            [result["selected_sku"]],
        )
        self.assertFalse(validation["valid"])
        self.assertIn("unsupported_capability:live_inventory", validation["reasons"])
        self.assertIn("unsupported_capability:reviews", validation["reasons"])

    def test_blocked_result_cannot_be_presented_as_a_recommendation(self):
        result = {
            "decision": "BLOCK",
            "selected_sku": None,
            "metadata": {"candidate_count": 0},
            "violations": ["max_price"],
        }
        evidence = build_recommendation_evidence(result, {"max_price": 500})
        validation = validate_recommendation_text(
            "I recommend Metro Cool Comfort anyway.",
            evidence,
            [{"sku_id": "S06", "name": "Metro Cool Comfort"}],
        )
        self.assertFalse(validation["valid"])
        self.assertIn(
            "blocked_outcome_presented_as_recommendation", validation["reasons"]
        )

    def test_constraint_relaxation_requires_structured_approval(self):
        result = {
            "decision": "ALLOW",
            "selected_sku": {"sku_id": "S06", "name": "Metro Cool Comfort"},
            "metadata": {},
            "violations": [],
        }
        unapproved = build_recommendation_evidence(result, {"max_price": 1000})
        approved = build_recommendation_evidence(
            result,
            {"max_price": 1100},
            approved_relaxation={"field": "max_price", "after": 1100},
        )
        text = "After you approved relaxing the limit, Metro Cool Comfort is the recommended mattress."
        self.assertFalse(
            validate_recommendation_text(text, unapproved, [result["selected_sku"]])[
                "valid"
            ]
        )
        self.assertTrue(
            validate_recommendation_text(text, approved, [result["selected_sku"]])[
                "valid"
            ]
        )

    def test_missing_fact_status_is_explicit_in_evidence(self):
        result = {
            "decision": "ALLOW",
            "selected_sku": {"sku_id": "S06", "name": "Metro Cool Comfort"},
            "metadata": {},
            "violations": [],
        }
        evidence = build_recommendation_evidence(result, {})
        self.assertIn("contains_latex", evidence["fact_status"]["unknown_product_facts"])
        self.assertIn("CA_haul_away", evidence["fact_status"]["unknown_service_facts"])


if __name__ == "__main__":
    unittest.main()
