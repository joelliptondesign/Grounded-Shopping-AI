import json
import unittest
from copy import deepcopy
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.data import SKU_CATALOG
from engine.preference_extraction import new_preference_state


def update(
    *,
    readiness,
    size=None,
    budget=None,
    cooling=None,
    motion=None,
    clarification=False,
    question=None,
    clarification_reason=None,
    browse=False,
):
    return {
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
            "explicit_browse_intent": browse,
        },
        "recovery_response": "none",
        "hard_constraints": {
            "size": size,
            "max_price": None,
            "exclude_latex": None,
            "require_CA_haul_away": None,
        },
        "soft_preferences": {
            "budget_target": budget,
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
            "cooling": cooling,
            "motion_isolation": motion,
        },
        "priorities": {
            "price": None,
            "firmness": None,
            "support": None,
            "cooling": "high" if cooling else None,
            "motion_isolation": "high" if motion else None,
        },
        "needs_clarification": clarification,
        "clarification_question": question,
        "clarification_reason": clarification_reason,
        "recommendation_readiness": readiness,
    }


class Client:
    def __init__(self, result):
        self.result = result
        self.responses = self
        self.request_names = []

    def create(self, **kwargs):
        self.request_names.append(
            (((kwargs.get("text") or {}).get("format") or {}).get("name"))
        )
        return SimpleNamespace(output_text=json.dumps(self.result))


class ColdStartTests(unittest.TestCase):
    def turn(self, message, extracted, state=None):
        return process_conversation_turn(
            message,
            deepcopy(state or new_preference_state()),
            SKU_CATALOG,
            client=Client(extracted),
        )

    def test_almost_no_signal_asks_size_and_budget_once(self):
        turn = self.turn(
            "I need a mattress.",
            update(
                readiness="low",
                clarification=True,
                question="What size are you shopping for, and roughly what would you like to spend?",
                clarification_reason="cold_start_basics",
            ),
        )
        self.assertEqual(turn["recommendation_readiness"], "low")
        self.assertEqual(turn["response_strategy"], "clarification")
        self.assertIn("size", turn["response_text"].casefold())
        self.assertIn("spend", turn["response_text"].casefold())
        self.assertIsNone(turn["decision_result"])
        elicitation = turn["presentation"]["elicitation"]
        self.assertEqual(elicitation["response_type"], "single_select")
        self.assertTrue(elicitation["allow_free_text"])
        self.assertTrue(elicitation["allow_skip"])
        self.assertEqual(
            [option["label"] for option in elicitation["options"]],
            ["Twin", "Twin XL", "Full", "Queen", "King", "Cal King"],
        )
        self.assertEqual(turn["elicitation_type"], "single_select")

    def test_size_only_asks_one_concise_budget_question_on_fresh_start(self):
        turn = self.turn(
            "I need a queen mattress.",
            update(
                readiness="low",
                size="queen",
                clarification=True,
                question="Roughly what would you like to spend?",
                clarification_reason="cold_start_basics",
            ),
        )
        self.assertEqual(turn["response_strategy"], "clarification")
        self.assertIn("spend", turn["response_text"].casefold())
        self.assertNotIn("firm", turn["response_text"].casefold())
        elicitation = turn["presentation"]["elicitation"]
        self.assertEqual(elicitation["id"], "mattress_budget_range_v1")
        self.assertEqual(
            [option["label"] for option in elicitation["options"]],
            ["Under $1,000", "$1,000–$1,250", "$1,250–$1,500", "$1,500+"],
        )
        for option in elicitation["options"]:
            self.assertNotIn(
                "max_price", option["structured_value"]["state_patch"].get("hard_constraints", {})
            )

    def test_budget_selection_updates_state_directly_and_clears_pending(self):
        first = self.turn(
            "I need a queen mattress.",
            update(
                readiness="low",
                size="queen",
                clarification=True,
                question="Roughly what would you like to spend?",
                clarification_reason="cold_start_basics",
            ),
        )
        resume_client = Client(update(readiness="low"))
        second = process_conversation_turn(
            "$1,250–$1,500",
            first["preference_state"],
            SKU_CATALOG,
            client=resume_client,
            elicitation_response={
                "elicitation_id": "mattress_budget_range_v1",
                "option_id": "1250_1500",
            },
        )
        self.assertEqual(second["modality"], "recommendation_cards")
        self.assertEqual(
            second["preference_state"]["soft_preferences"]["budget_target"], 1375
        )
        self.assertEqual(
            second["preference_state"]["soft_preferences"]["budget_flex_max"], 1500
        )
        self.assertIsNone(second["preference_state"]["hard_constraints"]["max_price"])
        self.assertIsNone(second["preference_state"]["pending_elicitation"])
        self.assertFalse(second["preference_state"]["needs_clarification"])
        self.assertEqual(second["structured_option_selected"]["id"], "1250_1500")
        self.assertNotIn("what amount", second["presentation"]["message"].casefold())
        self.assertNotIn("mattress_preference_update", resume_client.request_names)

    def test_show_me_options_skips_budget_and_does_not_repeat_question(self):
        first = self.turn(
            "I need a queen mattress.",
            update(
                readiness="low",
                size="queen",
                clarification=True,
                question="Roughly what would you like to spend?",
                clarification_reason="cold_start_basics",
            ),
        )
        second = process_conversation_turn(
            "Show me options",
            first["preference_state"],
            SKU_CATALOG,
            client=Client(update(readiness="low")),
            elicitation_response={
                "elicitation_id": "mattress_budget_range_v1",
                "action": "skip",
            },
        )
        self.assertEqual(second["modality"], "recommendation_cards")
        self.assertTrue(second["skipped_to_options"])
        self.assertIsNone(second["preference_state"]["pending_elicitation"])
        self.assertIsNone(second["presentation"]["elicitation"])

    def test_size_selection_applies_supported_value_without_model_interpretation(self):
        first = self.turn(
            "I need a mattress.",
            update(
                readiness="low",
                clarification=True,
                question="What size mattress are you shopping for?",
                clarification_reason="cold_start_basics",
            ),
        )
        second = process_conversation_turn(
            "King",
            first["preference_state"],
            SKU_CATALOG,
            client=Client(update(readiness="low")),
            elicitation_response={
                "elicitation_id": "mattress_size_v1",
                "option_id": "king",
            },
        )
        self.assertEqual(second["preference_state"]["hard_constraints"]["size"], "king")
        # Size landed deterministically; budget is the remaining basic, so the
        # agent spends its one follow-up on it before building a shortlist.
        self.assertEqual(second["response_strategy"], "clarification")
        self.assertEqual(
            second["preference_state"]["pending_elicitation"]["id"],
            "mattress_budget_range_v1",
        )

        third = process_conversation_turn(
            "Under $1,000",
            second["preference_state"],
            SKU_CATALOG,
            client=Client(update(readiness="exploratory")),
            elicitation_response={
                "elicitation_id": "mattress_budget_range_v1",
                "option_id": "under_1000",
            },
        )
        self.assertEqual(third["modality"], "recommendation_cards")
        self.assertIsNone(third["preference_state"]["pending_elicitation"])

    def test_free_text_answer_clears_pending_and_uses_normal_extraction(self):
        first = self.turn(
            "I need a queen mattress.",
            update(
                readiness="low",
                size="queen",
                clarification=True,
                question="Roughly what would you like to spend?",
                clarification_reason="cold_start_basics",
            ),
        )
        second = self.turn(
            "Probably around $1,800.",
            update(readiness="exploratory", budget=1800),
            first["preference_state"],
        )
        self.assertEqual(second["modality"], "recommendation_cards")
        self.assertEqual(
            second["preference_state"]["soft_preferences"]["budget_target"], 1800
        )
        self.assertIsNone(second["preference_state"]["pending_elicitation"])

    def test_size_and_budget_show_exploratory_products_immediately(self):
        turn = self.turn(
            "Queen around $1,500.",
            update(readiness="exploratory", size="queen", budget=1500),
        )
        self.assertEqual(turn["modality"], "recommendation_cards")
        self.assertEqual(
            turn["shopping_selection"]["selection_mode"],
            "exploratory_shortlist",
        )
        self.assertFalse(turn["preference_state"]["needs_clarification"])

    def test_strong_signal_recommends_without_cold_start_question(self):
        turn = self.turn(
            "Queen around $1,500. I sleep hot and my partner moves a lot.",
            update(
                readiness="strong",
                size="queen",
                budget=1500,
                cooling="higher",
                motion="higher",
            ),
        )
        self.assertEqual(turn["modality"], "recommendation_cards")
        self.assertFalse(turn["preference_state"]["needs_clarification"])
        self.assertEqual(turn["recommendation_readiness"], "strong")

    def test_explicit_browse_bypasses_low_readiness_clarification(self):
        turn = self.turn(
            "Just show me some queen mattresses.",
            update(
                readiness="low",
                size="queen",
                clarification=True,
                question="Roughly what would you like to spend?",
                clarification_reason="cold_start_basics",
                browse=True,
            ),
        )
        self.assertEqual(turn["modality"], "recommendation_cards")
        self.assertTrue(turn["explicit_browse_intent"])
        self.assertTrue(turn["clarification_bypassed"])
        self.assertEqual(
            turn["shopping_selection"]["selection_mode"],
            "exploratory_shortlist",
        )

    def test_missing_budget_gets_one_follow_up_after_combined_question(self):
        """Size and budget both markedly improve the first shortlist.

        A shopper who answers only the size half of the combined question is
        asked once for the other half, rather than being taken straight to
        results on half the signal.
        """
        state = new_preference_state()
        state.update(
            {
                "needs_clarification": True,
                "clarification_question": "What size, and roughly what would you like to spend?",
                "clarification_reason": "cold_start_basics",
                "recommendation_readiness": "low",
                "cold_start_questions_asked": 1,
            }
        )
        turn = self.turn(
            "King.",
            update(
                readiness="low",
                size="king",
                clarification=True,
                question="And what is your budget?",
                clarification_reason="cold_start_basics",
            ),
            state,
        )
        self.assertEqual(turn["response_strategy"], "clarification")
        self.assertFalse(turn["clarification_bypassed"])
        self.assertTrue(turn["preference_state"]["needs_clarification"])
        self.assertEqual(turn["preference_state"]["cold_start_questions_asked"], 2)

    def test_cold_start_never_asks_a_third_time(self):
        """Two attempts is the ceiling; the shortlist is never gated on basics."""
        state = new_preference_state()
        state.update(
            {
                "needs_clarification": True,
                "clarification_reason": "cold_start_basics",
                "recommendation_readiness": "low",
                "cold_start_questions_asked": 2,
            }
        )
        turn = self.turn(
            "King.",
            update(
                readiness="low",
                size="king",
                clarification=True,
                question="And what is your budget?",
                clarification_reason="cold_start_basics",
            ),
            state,
        )
        self.assertEqual(turn["modality"], "recommendation_cards")
        self.assertTrue(turn["clarification_bypassed"])
        self.assertFalse(turn["preference_state"]["needs_clarification"])

    def test_declining_the_basics_shows_options_immediately(self):
        """"I don't know" is an answer: stop asking and start shopping."""
        state = new_preference_state()
        state.update(
            {
                "needs_clarification": True,
                "clarification_reason": "cold_start_basics",
                "recommendation_readiness": "low",
                "cold_start_questions_asked": 1,
            }
        )
        turn = self.turn(
            "I don't know, budget doesn't matter.",
            update(
                readiness="low",
                size="king",
                clarification=True,
                question="And what is your budget?",
                clarification_reason="cold_start_basics",
            ),
            state,
        )
        self.assertEqual(turn["modality"], "recommendation_cards")
        self.assertTrue(turn["clarification_bypassed"])

    def test_product_reaction_updates_preference_and_refines_immediately(self):
        state = new_preference_state()
        state["hard_constraints"]["size"] = "queen"
        state["soft_preferences"]["budget_target"] = 1500
        state["recommendation_readiness"] = "exploratory"
        state["recent_product_names"] = ["Metro Cool Comfort", "Night Drift Hybrid"]
        turn = self.turn(
            "I like the second one, but I want something cooler.",
            update(readiness="strong", cooling="higher"),
            state,
        )
        self.assertEqual(turn["modality"], "recommendation_cards")
        self.assertEqual(
            turn["preference_state"]["directions"]["cooling"], "higher"
        )
        self.assertEqual(turn["recommendation_readiness"], "strong")


if __name__ == "__main__":
    unittest.main()
