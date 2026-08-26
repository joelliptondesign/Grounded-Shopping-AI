import json
import unittest
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision
from engine.grounding import build_recommendation_evidence, validate_recommendation_text
from engine.preference_extraction import new_preference_state
from engine.shopping_selection import (
    deterministic_selection_fallback,
    select_shopping_products,
    validate_shopping_selection,
)


def product(sku_id, price=1200, *, latex=False, cooling=7, motion=7, support=7):
    return {
        "sku_id": sku_id,
        "name": sku_id,
        "price": price,
        "available_sizes": ["king"],
        "contains_latex": latex,
        "haul_away_CA_available": True,
        "firmness": 6,
        "support": support,
        "cooling": cooling,
        "motion_isolation": motion,
    }


def extracted_update(**overrides):
    update = {
        "intent": "recommend",
        "turn_context": {
            "product_names": [], "product_attribute": None,
            "service_attribute": None, "exact_product_request": False,
            "information_source": None, "review_topic": None,
        },
        "recovery_response": "none",
        "hard_constraints": {
            "size": None, "max_price": None, "exclude_latex": None,
            "require_CA_haul_away": None,
        },
        "soft_preferences": {
            "budget_target": None, "budget_flex_max": None,
            "prefer_CA_haul_away": None, "firmness_target": None,
            "support_target": None, "cooling_target": None,
            "motion_isolation_target": None,
        },
        "directions": {
            "price": None, "firmness": None, "support": None,
            "cooling": None, "motion_isolation": None,
        },
        "priorities": {
            "price": None, "firmness": None, "support": None,
            "cooling": None, "motion_isolation": None,
        },
        "needs_clarification": False,
        "clarification_question": None,
    }
    for section, values in overrides.items():
        if isinstance(values, dict) and section in update:
            update[section].update(values)
        else:
            update[section] = values
    return update


class SequenceClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.responses = self
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(output_text=json.dumps(value))


class ShoppingSelectionTests(unittest.TestCase):
    def test_selection_rejects_products_outside_eligible_set(self):
        selection = {
            "selection_mode": "strong_recommendation",
            "primary_product_id": "OUT",
            "selections": [{"product_id": "OUT", "reason_tags": ["strong_overall_fit"]}],
        }
        validation = validate_shopping_selection(selection, [product("IN")], {})
        self.assertFalse(validation["valid"])
        self.assertIn("product_not_eligible:OUT", validation["reasons"])

    def test_unsafe_product_selection_is_rejected_even_if_supplied(self):
        unsafe = product("LATEX", latex=True)
        selection = {
            "selection_mode": "strong_recommendation",
            "primary_product_id": "LATEX",
            "selections": [{"product_id": "LATEX", "reason_tags": ["strong_overall_fit"]}],
        }
        validation = validate_shopping_selection(
            selection, [unsafe], {"exclude_latex": True}
        )
        self.assertFalse(validation["valid"])
        self.assertIn("hard_constraint_violation:LATEX", validation["reasons"])

    def test_unknown_fact_cannot_support_concrete_reason(self):
        unknown = product("UNKNOWN")
        unknown.pop("cooling")
        selection = {
            "selection_mode": "strong_recommendation",
            "primary_product_id": "UNKNOWN",
            "selections": [{"product_id": "UNKNOWN", "reason_tags": ["high_cooling"]}],
        }
        validation = validate_shopping_selection(selection, [unknown], {})
        self.assertFalse(validation["valid"])
        self.assertIn("unsupported_reason:UNKNOWN:high_cooling", validation["reasons"])

    def test_both_selection_modes_validate(self):
        candidates = [product("A"), product("B")]
        strong = {
            "selection_mode": "strong_recommendation", "primary_product_id": "A",
            "selections": [{"product_id": "A", "reason_tags": ["balanced_fit"]}],
        }
        exploratory = {
            "selection_mode": "exploratory_shortlist", "primary_product_id": None,
            "selections": [
                {"product_id": "B", "reason_tags": ["lower_price_option"]},
                {"product_id": "A", "reason_tags": ["premium_option"]},
            ],
        }
        candidates[0]["price"] = 1400
        candidates[1]["price"] = 1100
        self.assertTrue(validate_shopping_selection(strong, candidates, {})["valid"])
        self.assertTrue(validate_shopping_selection(exploratory, candidates, {})["valid"])

    def test_agent_selected_card_order_and_exploratory_certainty_are_preserved(self):
        update = extracted_update(
            soft_preferences={"budget_target": 2000, "budget_flex_max": 2500}
        )
        selection = {
            "selection_mode": "exploratory_shortlist",
            "primary_product_id": None,
            "selections": [
                {"product_id": "S02", "reason_tags": ["premium_option", "high_cooling"]},
                {"product_id": "S04", "reason_tags": ["balanced_fit"]},
                {"product_id": "S09", "reason_tags": ["lower_price_option", "strong_motion_isolation"]},
            ],
        }
        turn = process_conversation_turn(
            "Keep it around $2,000, but I could stretch to $2,500 for the right one.",
            new_preference_state(), SKU_CATALOG,
            client=SequenceClient([update, selection]),
        )
        self.assertEqual(turn["shopping_selection"]["selection_mode"], "exploratory_shortlist")
        self.assertIsNone(turn["shopping_selection"]["primary_product_id"])
        self.assertEqual(
            [item["sku_id"] for item in turn["presentation"]["products"]],
            ["S02", "S04", "S09"],
        )
        self.assertNotIn("strongest overall fit", turn["presentation"]["message"].casefold())
        self.assertNotEqual(turn["decision_result"]["selected_sku"]["sku_id"], "S02")

    def test_deterministic_fallback_is_safe_and_inspectable(self):
        decision = evaluate_decision({}, [product("A"), product("B")])
        fallback = select_shopping_products(
            decision, new_preference_state(), {}, "Help me choose",
            client=SequenceClient([RuntimeError("down"), RuntimeError("down")]),
        )
        self.assertTrue(fallback["fallback_used"])
        self.assertEqual(
            fallback["selected_product_ids"],
            [item["sku_id"] for item in decision["ranked_candidates"][:3]],
        )
        self.assertTrue(fallback["validation"]["valid"])

    def test_near_match_fallback_never_restores_hard_exclusion(self):
        decision = evaluate_decision(
            {"requested_size": "king", "exclude_latex": True, "budget_target": 900},
            [product("LATEX", 800, latex=True), product("SAFE", 1200)],
        )
        fallback = deterministic_selection_fallback(decision, new_preference_state())
        self.assertEqual(fallback["selected_product_ids"], ["SAFE"])

    def test_grounding_uses_validated_selection_not_scorer_top(self):
        decision = evaluate_decision({}, [product("SCORE_TOP"), product("AGENT_PICK", cooling=9)])
        selection = {
            "selection_mode": "strong_recommendation",
            "primary_product_id": "AGENT_PICK",
            "selections": [{"product_id": "AGENT_PICK", "reason_tags": ["high_cooling"]}],
            "selected_product_ids": ["AGENT_PICK"],
            "selection_reasons": {"AGENT_PICK": ["high_cooling"]},
            "validation": {"valid": True, "reasons": []},
        }
        evidence = build_recommendation_evidence(decision, {}, shopping_selection=selection)
        accepted = validate_recommendation_text(
            "I recommend AGENT_PICK.", evidence,
            [{"sku_id": "SCORE_TOP", "name": "SCORE_TOP"}, {"sku_id": "AGENT_PICK", "name": "AGENT_PICK"}],
        )
        rejected = validate_recommendation_text(
            "I recommend SCORE_TOP.", evidence,
            [{"sku_id": "SCORE_TOP", "name": "SCORE_TOP"}, {"sku_id": "AGENT_PICK", "name": "AGENT_PICK"}],
        )
        self.assertTrue(accepted["valid"])
        self.assertFalse(rejected["valid"])
        self.assertIn("different_product_recommended:SCORE_TOP", rejected["reasons"])

    def test_structured_cards_can_supply_product_identity_without_weakening_authority(self):
        decision = evaluate_decision({}, [product("A"), product("B"), product("OUT")])
        selection = {
            "selection_mode": "exploratory_shortlist",
            "primary_product_id": None,
            "selections": [
                {"product_id": "A", "reason_tags": ["balanced_fit"]},
                {"product_id": "B", "reason_tags": ["useful_tradeoff_option"]},
            ],
            "selected_product_ids": ["A", "B"],
            "selection_reasons": {"A": ["balanced_fit"], "B": ["useful_tradeoff_option"]},
        }
        evidence = build_recommendation_evidence(decision, {}, shopping_selection=selection)
        products = [
            {"sku_id": item, "name": item} for item in ("A", "B", "OUT")
        ]
        framing = validate_recommendation_text(
            "You've got room to choose based on what matters most.",
            evidence,
            products,
            structured_product_ids=["A", "B"],
        )
        substitution = validate_recommendation_text(
            "I recommend OUT.",
            evidence,
            products,
            structured_product_ids=["A", "B"],
        )
        self.assertTrue(framing["valid"])
        self.assertFalse(substitution["valid"])
        self.assertIn("different_product_recommended:OUT", substitution["reasons"])

    def test_good_use_of_budget_is_not_a_synonym_for_cheapest(self):
        candidates = [product("CHEAP", 875), product("MID", 1399), product("HIGH", 1479)]
        selection = {
            "selection_mode": "exploratory_shortlist",
            "primary_product_id": None,
            "selections": [
                {"product_id": "CHEAP", "reason_tags": ["good_use_of_budget", "lower_price_option"]},
                {"product_id": "MID", "reason_tags": ["balanced_fit"]},
                {"product_id": "HIGH", "reason_tags": ["premium_option"]},
            ],
        }
        validation = validate_shopping_selection(
            selection,
            candidates,
            {"budget_target": 2000, "budget_flex_max": 2500},
        )
        self.assertFalse(validation["valid"])
        self.assertIn("unsupported_reason:CHEAP:good_use_of_budget", validation["reasons"])

        selection["selections"][0]["reason_tags"] = ["lower_price_option", "good_value"]
        self.assertTrue(
            validate_shopping_selection(
                selection,
                candidates,
                {"budget_target": 2000, "budget_flex_max": 2500},
            )["valid"]
        )

    def test_compare_follow_up_selection_is_scoped_and_contextual(self):
        catalog = [
            product("OUTSIDE", 900, cooling=10),
            product("FIRST", 1200, cooling=9),
            product("SECOND", 1100, motion=9),
        ]
        update = extracted_update(
            turn_context={"product_names": ["FIRST", "SECOND"]},
            directions={"motion_isolation": "higher"},
            priorities={"motion_isolation": "critical"},
        )
        selection = {
            "selection_mode": "strong_recommendation",
            "primary_product_id": "SECOND",
            "selections": [
                {"product_id": "SECOND", "reason_tags": ["strong_motion_isolation"]},
                {"product_id": "FIRST", "reason_tags": ["high_cooling"]},
            ],
        }
        turn = process_conversation_turn(
            "Which one would you pick for me?",
            new_preference_state(), catalog,
            client=SequenceClient([update, selection]),
        )
        self.assertEqual(turn["shopping_selection"]["primary_product_id"], "SECOND")
        self.assertEqual(turn["shopping_selection"]["selected_product_ids"], ["SECOND", "FIRST"])
        self.assertNotIn("OUTSIDE", turn["shopping_selection"]["selected_product_ids"])


if __name__ == "__main__":
    unittest.main()
