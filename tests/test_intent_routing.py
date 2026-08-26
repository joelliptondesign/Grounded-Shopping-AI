import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from engine.conversation import process_conversation_turn
from engine.data import SKU_CATALOG
from engine.preference_extraction import EMPTY_STATE, INTENTS


def extracted_turn(
    intent,
    *,
    products=None,
    attribute=None,
    service_attribute=None,
    size=None,
    max_price=None,
    cooling=None,
    cooling_priority=None,
):
    return {
        "intent": intent,
        "turn_context": {
            "product_names": products or [],
            "product_attribute": attribute,
            "service_attribute": service_attribute,
        },
        "hard_constraints": {
            "size": size,
            "max_price": max_price,
            "exclude_latex": None,
            "require_CA_haul_away": None,
        },
        "soft_preferences": {
            "budget_target": None,
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
        "needs_clarification": False,
        "clarification_question": None,
    }


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.responses = self
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(output_text=json.dumps(self.result))


class IntentRoutingTests(unittest.TestCase):
    def route(self, message, result, state=None, **kwargs):
        return process_conversation_turn(
            message,
            deepcopy(state or EMPTY_STATE),
            SKU_CATALOG,
            client=FakeClient(result),
            **kwargs,
        )

    def test_taxonomy_is_exactly_phase_four_taxonomy(self):
        self.assertEqual(
            INTENTS,
            ("recommend", "compare", "product_question", "service_question", "off_topic"),
        )

    def test_recommendation_variations_route_to_existing_pipeline(self):
        for message in (
            "I need a king under $2,000 that sleeps cool.",
            "Find me a cool king mattress below two grand.",
        ):
            with self.subTest(message=message):
                turn = self.route(
                    message,
                    extracted_turn(
                        "recommend",
                        size="king",
                        max_price=2000,
                        cooling=9,
                        cooling_priority="high",
                    ),
                )
                self.assertEqual(turn["intent"], "recommend")
                self.assertEqual(turn["response_strategy"], "recommendation_pipeline")
                self.assertIsNotNone(turn["decision_result"])

    def test_explicit_comparison_uses_actual_catalog_data(self):
        turn = self.route(
            "How does Metro Cool Comfort compare with Urban Rest Core?",
            extracted_turn(
                "compare", products=["Metro Cool Comfort", "Urban Rest Core"]
            ),
        )
        self.assertEqual(turn["response_strategy"], "catalog_comparison")
        self.assertIsNone(turn["decision_result"])
        products = turn["grounding_data"]["products"]
        self.assertEqual([product["sku_id"] for product in products], ["S06", "S14"])
        self.assertEqual(products[0]["price"], 1099)
        self.assertEqual(products[1]["cooling"], 6)

    def test_product_attribute_question_uses_catalog_boolean(self):
        turn = self.route(
            "Is there latex in Metro Cool Comfort?",
            extracted_turn(
                "product_question",
                products=["Metro Cool Comfort"],
                attribute="contains_latex",
            ),
        )
        self.assertEqual(turn["response_strategy"], "catalog_fact_lookup")
        self.assertTrue(turn["grounding_data"]["verified"])
        self.assertIs(turn["grounding_data"]["value"], False)
        self.assertIn("not containing latex", turn["response_text"])

    def test_missing_product_attribute_is_not_inferred_false(self):
        turn = self.route(
            "Is Metro Cool Comfort organic certified?",
            extracted_turn(
                "product_question",
                products=["Metro Cool Comfort"],
                attribute="unknown",
            ),
        )
        self.assertFalse(turn["grounding_data"]["verified"])
        self.assertIsNone(turn["grounding_data"]["value"])
        self.assertIn("don't have reliable information", turn["response_text"])

    def test_service_question_uses_structured_service_data(self):
        turn = self.route(
            "Does Polar Motion Elite include haul-away in California?",
            extracted_turn(
                "service_question",
                products=["Polar Motion Elite"],
                service_attribute="haul_away",
            ),
        )
        fact = turn["grounding_data"]
        self.assertEqual(turn["response_strategy"], "service_fact_lookup")
        self.assertEqual(fact["product"]["sku_id"], "S02")
        self.assertTrue(fact["verified"])
        self.assertTrue(fact["available"])

    def test_product_scoped_inherited_service_topic_beats_generic_intent(self):
        turn = self.route(
            "What about Metro Cool Comfort?",
            extracted_turn(
                "product_question",
                products=["Metro Cool Comfort"],
                service_attribute="haul_away",
            ),
            conversation_history=[
                {"role": "user", "content": "Does Polar Motion Elite include California haul-away?"},
                {"role": "assistant", "content": "Yes—California haul-away is available for Polar Motion Elite."},
            ],
        )
        self.assertEqual(turn["intent"], "service_question")
        self.assertEqual(turn["response_strategy"], "service_fact_lookup")
        self.assertEqual(turn["grounding_data"]["product"]["sku_id"], "S06")
        self.assertFalse(turn["grounding_data"]["available"])

    def test_specific_product_attribute_beats_generic_service_intent(self):
        turn = self.route(
            "What about latex in Metro Cool Comfort?",
            extracted_turn(
                "service_question",
                products=["Metro Cool Comfort"],
                attribute="contains_latex",
            ),
        )
        self.assertEqual(turn["intent"], "product_question")
        self.assertEqual(turn["response_strategy"], "catalog_fact_lookup")

    def test_general_service_variation_uses_catalog_summary(self):
        turn = self.route(
            "Can you take away my old mattress?",
            extracted_turn("service_question", service_attribute="haul_away"),
        )
        self.assertEqual(turn["grounding_data"]["scope"], "catalog")
        self.assertGreater(len(turn["grounding_data"]["eligible_products"]), 0)

    def test_unrepresented_service_attribute_is_not_treated_as_haul_away(self):
        turn = self.route(
            "Does Metro Cool Comfort include in-home setup?",
            extracted_turn(
                "service_question",
                products=["Metro Cool Comfort"],
                service_attribute="unknown",
            ),
        )
        self.assertFalse(turn["grounding_data"]["verified"])
        self.assertIn("don't have reliable information", turn["response_text"])

    def test_off_topic_does_not_enter_recommendation_pipeline(self):
        with patch("engine.conversation.evaluate_decision") as decision:
            turn = self.route(
                "What's the weather tomorrow?", extracted_turn("off_topic")
            )
        decision.assert_not_called()
        self.assertEqual(turn["response_strategy"], "scoped_guardrail")
        self.assertIn("mattress", turn["response_text"])
        self.assertFalse(turn["scope_guardrail"]["in_scope"])

    def test_off_topic_copy_preserves_existing_shopping_context(self):
        state = deepcopy(EMPTY_STATE)
        state["recent_presentations"] = [
            {
                "modality": "recommendation_cards",
                "product_ids": ["S06", "S14"],
                "product_names": ["Metro Cool Comfort", "Night Drift Hybrid"],
            }
        ]

        turn = self.route(
            "What's the weather tomorrow?",
            extracted_turn("off_topic"),
            state=state,
        )

        self.assertIn("keep narrowing down those options", turn["response_text"])

    def test_normal_shopping_language_does_not_trigger_scope_guardrail(self):
        for message in (
            "My partner hates memory foam.",
            "I have back pain and sleep hot.",
            "This thing looks ugly. Is there another option?",
        ):
            with self.subTest(message=message):
                turn = self.route(message, extracted_turn("recommend"))
                self.assertTrue(turn["scope_guardrail"]["in_scope"])
                self.assertNotEqual(turn["response_strategy"], "scoped_guardrail")

    def test_recommendation_turn_exposes_structured_grounding_evidence(self):
        turn = self.route(
            "Recommend a cool queen mattress under $1,500.",
            extracted_turn("recommend", size="queen", max_price=1500, cooling=9),
        )
        evidence = turn["grounding_evidence"]
        self.assertEqual(
            evidence["authoritative_sources"]["recommendation"],
            "validated_shopping_agent_selection",
        )
        self.assertEqual(
            evidence["selected_sku"]["sku_id"],
            turn["decision_result"]["selected_sku"]["sku_id"],
        )
        self.assertIn("verified_product_facts", evidence["fact_status"])

    def test_intent_change_preserves_preferences_and_compare_does_not_rerank(self):
        state = deepcopy(EMPTY_STATE)
        state["hard_constraints"]["size"] = "king"
        state["hard_constraints"]["max_price"] = 2000
        state["soft_preferences"]["cooling_target"] = 9
        state["priorities"]["cooling"] = "critical"
        with patch("engine.conversation.evaluate_decision") as decision:
            turn = self.route(
                "Which is better for me, Metro Cool Comfort or Urban Rest Core?",
                extracted_turn(
                    "compare", products=["Metro Cool Comfort", "Urban Rest Core"]
                ),
                state,
            )
        decision.assert_not_called()
        self.assertEqual(turn["preference_state"]["hard_constraints"], state["hard_constraints"])
        self.assertEqual(turn["preference_state"]["priorities"], state["priorities"])

    def test_schema_constrains_intent_and_exposes_turn_context(self):
        client = FakeClient(extracted_turn("off_topic"))
        process_conversation_turn("Tell me a joke", deepcopy(EMPTY_STATE), SKU_CATALOG, client=client)
        schema = client.last_request["text"]["format"]["schema"]
        self.assertEqual(schema["properties"]["intent"]["enum"], list(INTENTS))
        self.assertIn("turn_context", schema["required"])


if __name__ == "__main__":
    unittest.main()
