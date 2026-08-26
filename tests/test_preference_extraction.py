import json
import unittest
from copy import deepcopy
from types import SimpleNamespace

from engine.conversation import process_recommendation_turn
from engine.data import SKU_CATALOG
from engine.preference_extraction import (
    EMPTY_STATE,
    extract_preference_state,
    extract_preference_update,
    merge_preference_state,
    new_preference_state,
    to_decision_preferences,
)


def update(
    *,
    intent=None,
    size=None,
    max_price=None,
    exclude_latex=None,
    require_haul_away=None,
    budget=None,
    firmness=None,
    support=None,
    cooling=None,
    motion=None,
    price_priority=None,
    firmness_priority=None,
    support_priority=None,
    cooling_priority=None,
    motion_priority=None,
    needs_clarification=False,
    clarification_question=None,
):
    return {
        "intent": intent,
        "hard_constraints": {
            "size": size,
            "max_price": max_price,
            "exclude_latex": exclude_latex,
            "require_CA_haul_away": require_haul_away,
        },
        "soft_preferences": {
            "budget_target": budget,
            "firmness_target": firmness,
            "support_target": support,
            "cooling_target": cooling,
            "motion_isolation_target": motion,
        },
        "priorities": {
            "price": price_priority,
            "firmness": firmness_priority,
            "support": support_priority,
            "cooling": cooling_priority,
            "motion_isolation": motion_priority,
        },
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
    }


class FakeResponses:
    def __init__(self, response_update):
        self.response_update = response_update
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(output_text=json.dumps(self.response_update))


class FakeClient:
    def __init__(self, response_update):
        self.responses = FakeResponses(response_update)


class PreferenceExtractionTests(unittest.TestCase):
    def extract(self, message, expected_update, state=None):
        client = FakeClient(expected_update)
        result = extract_preference_state(message, state, client=client)
        request = client.responses.last_request
        self.assertEqual(request["model"], "gpt-5.6-luna")
        self.assertEqual(request["reasoning"], {"effort": "none"})
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertTrue(request["text"]["format"]["strict"])
        return result

    def test_soft_budget_is_not_a_hard_maximum(self):
        state = self.extract(
            "I need a king around $2,000.",
            update(intent="recommend", size="king", budget=2000, price_priority="medium"),
        )
        self.assertEqual(state["soft_preferences"]["budget_target"], 2000)
        self.assertIsNone(state["hard_constraints"]["max_price"])
        self.assertIsNone(to_decision_preferences(state)["max_price"])

    def test_explicit_maximum_is_a_hard_constraint(self):
        state = self.extract(
            "I cannot go above $2,000.",
            update(intent="recommend", max_price=2000),
        )
        self.assertEqual(state["hard_constraints"]["max_price"], 2000)
        self.assertIsNone(state["priorities"]["price"])
        self.assertEqual(to_decision_preferences(state)["max_price"], 2000)

    def test_strong_cooling_priority(self):
        state = self.extract(
            "We sleep hot and cooling is really important.",
            update(intent="recommend", cooling=9, cooling_priority="critical"),
        )
        self.assertEqual(state["soft_preferences"]["cooling_target"], 9)
        self.assertEqual(state["priorities"]["cooling"], "critical")

    def test_relative_priority_instruction_preserves_ordering(self):
        client = FakeClient(
            update(
                motion_priority="critical",
                cooling_priority="medium",
            )
        )
        extract_preference_update(
            "Actually motion isolation matters more than cooling.",
            client=client,
        )
        system_prompt = client.responses.last_request["input"][0]["content"]
        self.assertIn("update both priority fields", system_prompt)
        self.assertIn("do not alter a hard constraint", system_prompt)

    def test_latex_exclusion_reaches_deterministic_gate_as_structured_data(self):
        state = self.extract(
            "No latex, please.",
            update(intent="recommend", exclude_latex=True),
        )
        preferences = to_decision_preferences(state)
        self.assertTrue(preferences["exclude_latex"])
        self.assertNotIn("query_text", preferences)

    def test_reversing_latex_exclusion_clears_structured_gate(self):
        state = new_preference_state()
        state["hard_constraints"]["exclude_latex"] = True
        state = merge_preference_state(state, update(exclude_latex=False))

        self.assertFalse(state["hard_constraints"]["exclude_latex"])
        self.assertFalse(to_decision_preferences(state)["exclude_latex"])

    def test_required_haul_away_reaches_existing_service_gate(self):
        state = self.extract(
            "California haul-away is required.",
            update(intent="recommend", require_haul_away=True),
        )
        self.assertTrue(to_decision_preferences(state)["require_CA_haul_away"])

    def test_service_question_is_not_automatically_a_requirement(self):
        state = self.extract(
            "Do you offer haul-away in California?",
            update(intent="service_question"),
        )
        self.assertEqual(state["intent"], "service_question")
        self.assertIsNone(state["hard_constraints"]["require_CA_haul_away"])
        self.assertFalse(to_decision_preferences(state)["require_CA_haul_away"])

    def test_existing_preference_updates_across_turns(self):
        first = self.extract(
            "A king around $2,000 with excellent cooling.",
            update(
                intent="recommend",
                size="king",
                budget=2000,
                cooling=9,
                cooling_priority="critical",
            ),
        )
        second = self.extract(
            "Actually $2,400 is my absolute max, but cooling matters much more than price.",
            update(max_price=2400, price_priority="low", cooling_priority="critical"),
            first,
        )
        self.assertEqual(second["hard_constraints"]["max_price"], 2400)
        self.assertEqual(second["soft_preferences"]["budget_target"], 2000)
        self.assertEqual(second["priorities"]["price"], "low")
        self.assertEqual(second["priorities"]["cooling"], "critical")
        preferences = to_decision_preferences(second)
        self.assertEqual(preferences["max_price"], 2400)
        self.assertEqual(preferences["priorities"]["price"], "low")
        self.assertEqual(preferences["priorities"]["cooling"], "critical")

    def test_changing_one_preference_preserves_prior_state(self):
        state = new_preference_state()
        state["hard_constraints"]["size"] = "queen"
        state["hard_constraints"]["exclude_latex"] = True
        state["soft_preferences"]["cooling_target"] = 8
        state["priorities"]["cooling"] = "high"

        merged = merge_preference_state(
            state,
            update(firmness=6, firmness_priority="medium"),
        )
        self.assertEqual(merged["hard_constraints"]["size"], "queen")
        self.assertTrue(merged["hard_constraints"]["exclude_latex"])
        self.assertEqual(merged["soft_preferences"]["cooling_target"], 8)
        self.assertEqual(merged["soft_preferences"]["firmness_target"], 6)

    def test_blocking_ambiguity_requests_clarification_and_skips_decision(self):
        response_update = update(
            intent="recommend",
            needs_clarification=True,
            clarification_question="Should I treat $2,000 or $2,500 as your maximum?",
        )
        turn = process_recommendation_turn(
            "Keep it under $2,000—or maybe $2,500 is the real cap.",
            None,
            SKU_CATALOG,
            client=FakeClient(response_update),
        )
        self.assertTrue(turn["preference_state"]["needs_clarification"])
        self.assertIsNone(turn["decision_result"])

    def test_ordinary_missing_fields_do_not_trigger_clarification(self):
        state = self.extract(
            "I'd like a queen mattress.",
            update(intent="recommend", size="queen"),
        )
        self.assertFalse(state["needs_clarification"])
        self.assertIsNone(state["clarification_question"])

    def test_integration_applies_dynamic_weights(self):
        response_update = update(
            intent="recommend",
            max_price=1400,
            cooling=8,
            cooling_priority="high",
        )
        turn = process_recommendation_turn(
            "I need strong cooling and cannot spend over $1,400.",
            deepcopy(EMPTY_STATE),
            SKU_CATALOG,
            client=FakeClient(response_update),
        )
        self.assertEqual(turn["decision_result"]["decision"], "ALLOW")
        self.assertGreater(
            turn["decision_result"]["metadata"]["active_normalized_weights"]["cooling"],
            0.20,
        )
        self.assertEqual(turn["decision_preferences"]["max_price"], 1400)

    def test_target_and_priority_remain_independent(self):
        state = new_preference_state()
        state["soft_preferences"]["cooling_target"] = 9
        state["priorities"]["cooling"] = "medium"

        changed = merge_preference_state(
            state,
            update(cooling_priority="critical"),
        )
        preferences = to_decision_preferences(changed)
        self.assertEqual(preferences["cooling_preference"], 9)
        self.assertEqual(preferences["priorities"]["cooling"], "critical")

    def test_priority_only_turn_preserves_hard_constraints(self):
        state = new_preference_state()
        state["hard_constraints"]["size"] = "king"
        state["hard_constraints"]["max_price"] = 2400
        state["hard_constraints"]["exclude_latex"] = True
        merged = merge_preference_state(
            state,
            update(price_priority="low", cooling_priority="critical"),
        )
        self.assertEqual(merged["hard_constraints"], state["hard_constraints"])

    def test_empty_message_is_rejected_before_api_call(self):
        with self.assertRaises(ValueError):
            extract_preference_update(" ", client=FakeClient(update()))


if __name__ == "__main__":
    unittest.main()
