import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from engine.conversation import process_conversation_turn
from engine.decision import evaluate_decision
from engine.preference_extraction import new_preference_state
from engine.response_strategy import build_product_fact, build_service_fact


def extracted(
    *,
    intent="recommend",
    products=None,
    exact_product=False,
    size=None,
    max_price=None,
    exclude_latex=None,
    haul_away=None,
    budget=None,
    cooling=None,
    cooling_priority=None,
    clarification=False,
    question=None,
    recovery_response="none",
):
    return {
        "intent": intent,
        "turn_context": {
            "product_names": products or [],
            "product_attribute": None,
            "service_attribute": None,
            "exact_product_request": exact_product,
        },
        "recovery_response": recovery_response,
        "hard_constraints": {
            "size": size,
            "max_price": max_price,
            "exclude_latex": exclude_latex,
            "require_CA_haul_away": haul_away,
        },
        "soft_preferences": {
            "budget_target": budget,
            "firmness_target": None,
            "support_target": None,
            "cooling_target": cooling,
            "motion_isolation_target": None,
        },
        "priorities": {
            "price": None,
            "firmness": None,
            "support": None,
            "cooling": cooling_priority,
            "motion_isolation": None,
        },
        "needs_clarification": clarification,
        "clarification_question": question,
    }


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.responses = self

    def create(self, **kwargs):
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=json.dumps(self.result))


def sku(
    sku_id,
    *,
    price=1000,
    sizes=None,
    haul_away=True,
    include_service=True,
    include_latex=True,
):
    item = {
        "sku_id": sku_id,
        "name": sku_id,
        "price": price,
        "available_sizes": sizes or ["king"],
        "firmness": 6,
        "support": 7,
        "cooling": 8,
        "motion_isolation": 8,
    }
    if include_service:
        item["haul_away_CA_available"] = haul_away
    if include_latex:
        item["contains_latex"] = False
    return item


class RecoveryTests(unittest.TestCase):
    def turn(self, message, result, state=None, catalog=None, previous=None):
        return process_conversation_turn(
            message,
            deepcopy(state) if state is not None else new_preference_state(),
            catalog or [sku("S1")],
            client=FakeClient(result),
            previous_decision_result=previous,
        )

    def test_ambiguous_hard_ceiling_clarifies_without_decision(self):
        turn = self.turn(
            "Keep it under $2,000, although maybe $2,500 is my max.",
            extracted(
                clarification=True,
                question="Should I treat $2,000 or $2,500 as your maximum?",
            ),
        )
        self.assertEqual(turn["recovery"]["recovery_type"], "clarification")
        self.assertIsNone(turn["decision_result"])
        self.assertIsNone(turn["preference_state"]["hard_constraints"]["max_price"])

    def test_soft_budget_and_missing_optional_preferences_do_not_clarify(self):
        turn = self.turn(
            "I'd like to stay around $2,000.", extracted(budget=2000)
        )
        self.assertFalse(turn["preference_state"]["needs_clarification"])
        self.assertIsNone(turn["decision_preferences"]["max_price"])
        self.assertEqual(turn["decision_result"]["decision"], "ALLOW")

    def test_exact_product_conflicting_with_saved_budget_requests_approval(self):
        state = new_preference_state()
        state["hard_constraints"]["max_price"] = 1500
        turn = self.turn(
            "Only show me the Premium model.",
            extracted(products=["Premium"], exact_product=True),
            state,
            [sku("PREMIUM", price=1799)],
        )
        self.assertEqual(turn["recovery"]["recovery_type"], "conflicting_requirements")
        self.assertIn("$1,500", turn["response_text"])
        self.assertEqual(turn["preference_state"]["hard_constraints"]["max_price"], 1500)
        self.assertIsNone(turn["decision_result"])

    def test_no_match_never_recommends_invalid_sku_and_proposal_is_grounded(self):
        catalog = [sku("OVER", price=1800), sku("NO_SERVICE", price=1400, haul_away=False)]
        turn = self.turn(
            "King under $1,500 with haul-away.",
            extracted(size="king", max_price=1500, haul_away=True),
            catalog=catalog,
        )
        self.assertEqual(turn["decision_result"]["decision"], "BLOCK")
        self.assertIsNone(turn["decision_result"]["selected_sku"])
        proposal = turn["recovery"]["proposed_relaxation"]
        self.assertEqual(proposal["type"], "relax_max_price")
        self.assertEqual(proposal["proposed_value"], 1800)
        self.assertEqual(proposal["match_count"], 1)
        self.assertEqual(turn["preference_state"]["hard_constraints"]["max_price"], 1500)

    def test_approval_updates_constraint_and_resumes_recommendation(self):
        catalog = [sku("MATCH", price=1800)]
        first = self.turn(
            "King under $1,500 with haul-away.",
            extracted(size="king", max_price=1500, haul_away=True),
            catalog=catalog,
        )
        second = self.turn(
            "Yes, raise it.",
            extracted(recovery_response="approve"),
            first["preference_state"],
            catalog,
            first["decision_result"],
        )
        self.assertEqual(second["preference_state"]["hard_constraints"]["max_price"], 1800)
        self.assertIsNone(second["preference_state"]["pending_recovery"])
        self.assertEqual(second["decision_result"]["decision"], "ALLOW")
        self.assertEqual(second["decision_result"]["selected_sku"]["sku_id"], "MATCH")

    def test_rejected_relaxation_preserves_original_constraint(self):
        catalog = [sku("MATCH", price=1800)]
        first = self.turn(
            "King under $1,500 with haul-away.",
            extracted(size="king", max_price=1500, haul_away=True),
            catalog=catalog,
        )
        second = self.turn(
            "No, keep the limit.",
            extracted(recovery_response="reject"),
            first["preference_state"],
            catalog,
            first["decision_result"],
        )
        self.assertEqual(second["preference_state"]["hard_constraints"]["max_price"], 1500)
        self.assertIsNone(second["decision_result"])

    def test_missing_product_and_service_data_remain_unknown(self):
        product = sku("UNKNOWN", include_latex=False, include_service=False)
        product_fact = build_product_fact(["UNKNOWN"], "contains_latex", [product])
        service_fact = build_service_fact(
            ["UNKNOWN"], [product], service_attribute="haul_away"
        )
        self.assertFalse(product_fact["verified"])
        self.assertIsNone(product_fact["value"])
        self.assertFalse(service_fact["verified"])
        self.assertIsNone(service_fact["available"])

        decision = evaluate_decision({"require_CA_haul_away": True}, [product])
        exclusion = decision["metadata"]["excluded_candidates"][0]
        self.assertEqual(exclusion["violations"], [])
        self.assertEqual(exclusion["unknowns"], ["unknown_require_CA_haul_away"])

        turn = self.turn(
            "Haul-away is required.",
            extracted(haul_away=True),
            catalog=[product],
        )
        self.assertEqual(turn["recovery"]["recovery_type"], "missing_data")
        self.assertIn("couldn't verify", turn["response_text"])
        self.assertNotIn("not available", turn["response_text"])

    def test_hard_and_soft_corrections_preserve_unrelated_state(self):
        state = new_preference_state()
        state["hard_constraints"].update({"size": "king", "max_price": 2000})
        state["soft_preferences"]["cooling_target"] = 9
        state["priorities"]["cooling"] = "critical"
        previous = evaluate_decision(
            {"requested_size": "king", "max_price": 2000}, [sku("S1")]
        )

        soft = self.turn(
            "Cooling isn't that important after all.",
            extracted(cooling_priority="low"),
            state,
            previous=previous,
        )
        self.assertEqual(soft["preference_state"]["hard_constraints"], state["hard_constraints"])
        self.assertFalse(soft["pipeline_actions"]["eligibility_recomputed"])
        self.assertTrue(soft["pipeline_actions"]["ranking_recomputed"])

        hard = self.turn(
            "No, I meant queen, not king.", extracted(size="queen"), state
        )
        self.assertEqual(hard["preference_state"]["hard_constraints"]["size"], "queen")
        self.assertEqual(hard["preference_state"]["hard_constraints"]["max_price"], 2000)
        self.assertEqual(hard["preference_state"]["soft_preferences"]["cooling_target"], 9)
        self.assertTrue(hard["pipeline_actions"]["eligibility_recomputed"])

    def test_extraction_failure_preserves_state_and_skips_decision(self):
        state = new_preference_state()
        state["hard_constraints"]["size"] = "queen"
        with patch("engine.conversation.evaluate_decision") as decision:
            turn = process_conversation_turn(
                "Actually make that king.",
                state,
                [sku("S1")],
                client=FakeClient(error=TimeoutError("model timed out")),
            )
        decision.assert_not_called()
        self.assertEqual(turn["preference_state"], state)
        self.assertEqual(turn["recovery"]["recovery_type"], "extraction_failure")
        self.assertEqual(turn["extraction_error"]["type"], "TimeoutError")
        self.assertNotIn("timed out", turn["response_text"])

    def test_invalid_model_payload_is_recovered_without_decision(self):
        with patch("engine.conversation.evaluate_decision") as decision:
            turn = process_conversation_turn(
                "Update my budget.",
                new_preference_state(),
                [sku("S1")],
                client=FakeClient({"intent": "not_valid"}),
            )
        decision.assert_not_called()
        self.assertEqual(turn["recovery"]["recovery_type"], "extraction_failure")


if __name__ == "__main__":
    unittest.main()
