import json
import unittest
from copy import deepcopy
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.data import SKU_CATALOG
from engine.preference_extraction import new_preference_state


def update(
    action,
    product_ids=None,
    *,
    intent=None,
    product_attribute=None,
    service_attribute=None,
    information_source=None,
    review_topic=None,
    clarification=None,
):
    intent = intent or {
        "recommend_products": "recommend",
        "compare_products": "compare",
        "choose_from_products": "recommend",
        "answer_product_question": "product_question",
        "answer_service_question": "service_question",
        "off_topic": "off_topic",
        "clarify_reference": "product_question",
    }[action]
    return {
        "intent": intent,
        "shopping_action": {
            "action": action,
            "product_ids": list(product_ids or []),
            "product_attribute": product_attribute,
            "service_attribute": service_attribute,
        },
        "turn_context": {
            "product_names": list(product_ids or []),
            "product_attribute": product_attribute,
            "service_attribute": service_attribute,
            "exact_product_request": False,
            "information_source": information_source,
            "review_topic": review_topic,
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
        "needs_clarification": clarification is not None,
        "clarification_question": clarification,
    }


def selection(*product_ids, primary=None):
    return {
        "selection_mode": "strong_recommendation",
        "primary_product_id": primary or product_ids[0],
        "selections": [
            {"product_id": product_id, "reason_tags": ["strong_overall_fit"]}
            for product_id in product_ids
        ],
    }


class SchemaClient:
    def __init__(self, extraction, shopping_selection=None):
        self.extraction = extraction
        self.shopping_selection = shopping_selection or selection("S06")
        self.responses = self
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        name = kwargs.get("text", {}).get("format", {}).get("name")
        value = self.shopping_selection if name == "shopping_product_selection" else self.extraction
        return SimpleNamespace(output_text=json.dumps(value))


class ConversationalReferenceTests(unittest.TestCase):
    def route(self, message, state, extraction, *, previous=None, shopping_selection=None, history=None):
        client = SchemaClient(extraction, shopping_selection)
        turn = process_conversation_turn(
            message,
            deepcopy(state),
            SKU_CATALOG,
            client=client,
            previous_decision_result=previous,
            conversation_history=history or [],
        )
        return turn, client

    def cards_state(self):
        state = new_preference_state()
        state["recent_presentations"] = [
            {
                "modality": "recommendation_cards",
                "product_ids": ["S06", "S14", "S03"],
                "product_names": [
                    "Metro Cool Comfort",
                    "Urban Rest Core",
                    "Harbor Plush",
                ],
                "action": "recommend_products",
                "product_attribute": None,
                "service_attribute": None,
                "information_source": None,
                "review_topic": None,
            }
        ]
        state["recent_product_names"] = [
            "Metro Cool Comfort",
            "Urban Rest Core",
            "Harbor Plush",
        ]
        return state

    def comparison_state(self):
        state = self.cards_state()
        state["directions"]["cooling"] = "higher"
        state["priorities"]["cooling"] = "critical"
        state["recent_presentations"].append(
            {
                "modality": "comparison_table",
                "product_ids": ["S06", "S14"],
                "product_names": ["Metro Cool Comfort", "Urban Rest Core"],
                "action": "compare_products",
                "product_attribute": None,
                "service_attribute": None,
                "information_source": None,
                "review_topic": None,
            }
        )
        return state

    def test_cards_to_ordinal_comparison_uses_display_order(self):
        turn, client = self.route(
            "Compare the first two.",
            self.cards_state(),
            update("compare_products", ["S06", "S14"]),
        )
        self.assertEqual(turn["shopping_action"]["action"], "compare_products")
        self.assertEqual(turn["shopping_action"]["product_ids"], ["S06", "S14"])
        self.assertEqual(turn["modality"], "comparison_table")
        self.assertIsNone(turn["recovery"])
        payload = json.loads(client.requests[0]["input"][1]["content"])
        self.assertEqual(
            payload["recent_presentation_results"]["recent_presentations"][0]["product_ids"],
            ["S06", "S14", "S03"],
        )

    def test_comparison_to_pick_stays_inside_choice_set_and_preserves_state(self):
        state = self.comparison_state()
        turn, _ = self.route(
            "Which one would you pick for me?",
            state,
            update("choose_from_products", ["S06", "S14"]),
            shopping_selection=selection("S06", primary="S06"),
        )
        self.assertEqual(turn["shopping_action"]["action"], "choose_from_products")
        self.assertEqual(turn["shopping_action"]["product_ids"], ["S06", "S14"])
        self.assertEqual(
            {item["sku_id"] for item in turn["decision_result"]["ranked_candidates"]},
            {"S06", "S14"},
        )
        self.assertEqual(turn["shopping_selection"]["primary_product_id"], "S06")
        self.assertEqual(turn["preference_state"]["priorities"]["cooling"], "critical")
        self.assertIsNone(turn["recovery"])

    def test_comparison_to_attribute_remains_scoped(self):
        turn, _ = self.route(
            "Which one is cooler?",
            self.comparison_state(),
            update("compare_products", ["S06", "S14"], product_attribute="cooling"),
        )
        self.assertEqual(turn["intent"], "compare")
        self.assertEqual(
            [item["sku_id"] for item in turn["grounding_data"]["products"]],
            ["S06", "S14"],
        )
        self.assertIsNone(turn["recovery"])

    def test_comparison_to_second_one_resolves_single_product(self):
        turn, _ = self.route(
            "What about the second one?",
            self.comparison_state(),
            update("answer_product_question", ["S14"]),
        )
        self.assertEqual(turn["shopping_action"]["product_ids"], ["S14"])
        self.assertEqual(turn["grounding_data"]["product"]["sku_id"], "S14")

    def test_review_pronoun_preserves_product_and_review_topic(self):
        state = new_preference_state()
        first, _ = self.route(
            "What do owners say about Metro Cool Comfort?",
            state,
            update(
                "answer_product_question",
                ["S06"],
                information_source="reviews",
                review_topic="general",
            ),
        )
        second, _ = self.route(
            "Does it sleep hot?",
            first["preference_state"],
            update(
                "answer_product_question",
                ["S06"],
                product_attribute="cooling",
                information_source="reviews",
                review_topic="cooling",
            ),
        )
        self.assertEqual(second["shopping_action"]["product_ids"], ["S06"])
        self.assertEqual(second["grounding_data"]["requested_topic"], "cooling")
        self.assertEqual(second["response_strategy"], "review_evidence_lookup")

    def test_service_product_switch_preserves_haul_away_topic(self):
        first, _ = self.route(
            "Does Polar Motion Elite include haul-away?",
            new_preference_state(),
            update("answer_service_question", ["S02"], service_attribute="haul_away"),
        )
        second, _ = self.route(
            "What about Metro Cool Comfort?",
            first["preference_state"],
            update("answer_service_question", ["S06"], service_attribute="haul_away"),
        )
        self.assertEqual(second["intent"], "service_question")
        self.assertEqual(second["grounding_data"]["product"]["sku_id"], "S06")
        self.assertFalse(second["grounding_data"]["available"])

    def test_genuine_ambiguity_asks_one_natural_clarification_without_state_loss(self):
        state = self.cards_state()
        state["hard_constraints"]["size"] = "queen"
        question = "Do you mean Metro Cool Comfort or Urban Rest Core?"
        turn, _ = self.route(
            "What about that other one?",
            state,
            update("clarify_reference", clarification=question),
        )
        self.assertEqual(turn["response_strategy"], "clarification")
        self.assertEqual(turn["response_text"], question)
        self.assertNotIn("reference", turn["response_text"].casefold())
        self.assertEqual(turn["preference_state"]["hard_constraints"]["size"], "queen")

    def test_invalid_compare_pick_identity_is_repaired_from_authoritative_ui(self):
        turn, client = self.route(
            "Which one would you pick for me?",
            self.comparison_state(),
            update("choose_from_products", ["NOT-A-SKU", "ALSO-NOT-A-SKU"]),
            shopping_selection=selection("S06", primary="S06"),
        )
        extraction_calls = [
            request
            for request in client.requests
            if request.get("text", {}).get("format", {}).get("name")
            == "mattress_preference_update"
        ]
        self.assertEqual(len(extraction_calls), 2)
        self.assertEqual(turn["shopping_action"]["product_ids"], ["S06", "S14"])
        self.assertTrue(turn["shopping_action_validation"]["valid"])
        self.assertIsNone(turn["recovery"])


if __name__ == "__main__":
    unittest.main()
