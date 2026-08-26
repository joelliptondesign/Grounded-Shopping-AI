import json
import unittest
from copy import deepcopy
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.decision import evaluate_decision, score_dimensions
from engine.preference_extraction import extract_preference_update, new_preference_state


def product(sku_id, price, *, latex=False, haul=True, size="king", cooling=7, motion=7):
    return {
        "sku_id": sku_id,
        "name": sku_id,
        "price": price,
        "available_sizes": [size],
        "contains_latex": latex,
        "haul_away_CA_available": haul,
        "firmness": 6,
        "support": 7,
        "cooling": cooling,
        "motion_isolation": motion,
    }


def update(**overrides):
    value = {
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
    for section, fields in overrides.items():
        if isinstance(fields, dict) and isinstance(value.get(section), dict):
            value[section].update(fields)
        else:
            value[section] = fields
    return value


class Client:
    def __init__(self, result):
        self.result = result
        self.responses = self
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_text=json.dumps(self.result))


class V2ShoppingBehaviorTests(unittest.TestCase):
    def test_flexible_budget_and_haul_away_produce_near_matches(self):
        catalog = [
            product("SERVICE", 1275, haul=True),
            product("BUDGET", 875, haul=False),
        ]
        client = Client(update(
            hard_constraints={"size": "king"},
            soft_preferences={"budget_target": 900, "prefer_CA_haul_away": True},
        ))
        turn = process_conversation_turn(
            "I need a king under $900 with California haul-away.",
            new_preference_state(), catalog, client=client,
        )
        self.assertEqual(turn["decision_result"]["decision"], "ALLOW")
        self.assertEqual(turn["decision_result"]["match_type"], "near_match")
        self.assertEqual(turn["modality"], "recommendation_cards")
        tradeoffs = {item["sku_id"]: item["tradeoff"] for item in turn["presentation"]["products"]}
        self.assertIn("above your preferred budget", tradeoffs["SERVICE"])
        self.assertIn("Doesn't include", tradeoffs["BUDGET"])
        self.assertIsNone(turn["preference_state"]["pending_recovery"])

    def test_hard_budget_still_blocks_over_budget_product(self):
        decision = evaluate_decision(
            {"requested_size": "king", "max_price": 900},
            [product("OVER", 1000)],
        )
        self.assertEqual(decision["decision"], "BLOCK")
        self.assertIsNone(decision["selected_sku"])

    def test_near_matches_never_weaken_latex_exclusion(self):
        decision = evaluate_decision(
            {
                "requested_size": "king", "exclude_latex": True,
                "budget_target": 900,
            },
            [product("LATEX", 800, latex=True), product("SAFE", 1149)],
        )
        self.assertEqual(decision["selected_sku"]["sku_id"], "SAFE")
        self.assertEqual(decision["match_type"], "near_match")
        self.assertNotIn("LATEX", [item["sku_id"] for item in decision["ranked_candidates"]])

    def test_single_safe_latex_free_candidate_is_a_strong_singular_recommendation(self):
        catalog = [
            product("SAFE", 1149, latex=False),
            product("LATEX", 850, latex=True),
        ]
        turn = process_conversation_turn(
            "I'm looking for a king around $1,200, and I'm allergic to latex.",
            new_preference_state(),
            catalog,
            client=Client(
                update(
                    hard_constraints={"size": "king", "exclude_latex": True},
                    soft_preferences={"budget_target": 1200},
                )
            ),
        )
        selection = turn["shopping_selection"]
        self.assertEqual(selection["selection_mode"], "strong_recommendation")
        self.assertEqual(selection["primary_product_id"], "SAFE")
        self.assertEqual(selection["selected_product_ids"], ["SAFE"])
        self.assertIn("latex-free", turn["presentation"]["message"].casefold())
        self.assertIn(
            "Verified latex-free",
            turn["presentation"]["products"][0]["why_it_matches"],
        )
        self.assertNotIn("these options", turn["presentation"]["message"].casefold())

    def test_directional_cooling_uses_more_is_better_without_target(self):
        preferences = {"directions": {"cooling": "higher"}}
        self.assertGreater(
            score_dimensions(preferences, product("COOL", 1000, cooling=9))["cooling"],
            score_dimensions(preferences, product("WARM", 1000, cooling=5))["cooling"],
        )

    def test_numeric_firmness_remains_a_target(self):
        preferences = {
            "firmness_preference": 6,
            "directions": {"firmness": "higher"},
        }
        six = product("SIX", 1000)
        nine = product("NINE", 1000)
        nine["firmness"] = 9
        self.assertGreater(
            score_dimensions(preferences, six)["firmness"],
            score_dimensions(preferences, nine)["firmness"],
        )

    def test_extraction_receives_only_last_eight_history_items(self):
        client = Client(update())
        history = [{"role": "user", "content": str(index)} for index in range(12)]
        extract_preference_update(
            "Does it sleep hot?", new_preference_state(), client=client,
            conversation_history=history,
            recent_results={"displayed_product_names": ["Metro Cool Comfort"]},
        )
        payload = json.loads(client.request["input"][1]["content"])
        self.assertEqual(len(payload["recent_conversation"]), 8)
        self.assertEqual(payload["recent_conversation"][0]["content"], "4")
        self.assertEqual(
            payload["recent_presentation_results"]["displayed_product_names"],
            ["Metro Cool Comfort"],
        )

    def test_size_correction_preserves_directional_preference(self):
        state = new_preference_state()
        state["hard_constraints"]["size"] = "king"
        state["directions"]["cooling"] = "higher"
        state["priorities"]["cooling"] = "critical"
        turn = process_conversation_turn(
            "Sorry, I meant queen.", state, [product("Q", 1000, size="queen")],
            client=Client(update(hard_constraints={"size": "queen"})),
        )
        self.assertEqual(turn["preference_state"]["hard_constraints"]["size"], "queen")
        self.assertEqual(turn["preference_state"]["directions"]["cooling"], "higher")

    def test_flexible_ceiling_proceeds_without_clarification(self):
        turn = process_conversation_turn(
            "Keep it under $2,000, or maybe $2,500 is my real max.",
            new_preference_state(), [product("ONE", 2200)],
            client=Client(update(soft_preferences={"budget_target": 2000, "budget_flex_max": 2500})),
        )
        self.assertFalse(turn["preference_state"]["needs_clarification"])
        self.assertIsNone(turn["preference_state"]["hard_constraints"]["max_price"])
        self.assertEqual(turn["decision_result"]["decision"], "ALLOW")

    def test_upper_flexibility_keeps_stronger_option_in_primary_group(self):
        decision = evaluate_decision(
            {
                "budget_target": 2000,
                "budget_flex_max": 2500,
                "directions": {"cooling": "higher"},
                "priorities": {"cooling": "critical"},
            },
            [
                product("TARGET", 1900, cooling=5),
                product("FLEX", 2300, cooling=10),
            ],
        )
        self.assertEqual(decision["selected_sku"]["sku_id"], "FLEX")
        self.assertEqual(decision["match_type"], "exact_or_ranked")
        self.assertTrue(decision["metadata"]["preference_tradeoffs"]["FLEX"])

    def test_follow_up_pick_is_scoped_to_compared_products(self):
        state = new_preference_state()
        state["directions"]["cooling"] = "higher"
        state["priorities"]["cooling"] = "critical"
        catalog = [
            product("OUTSIDE", 900, cooling=10),
            product("FIRST", 1200, cooling=9),
            product("SECOND", 1100, cooling=7),
        ]
        turn = process_conversation_turn(
            "Which one would you pick for me?", state, catalog,
            client=Client(update(
                turn_context={"product_names": ["FIRST", "SECOND"]},
            )),
        )
        self.assertEqual(turn["decision_result"]["selected_sku"]["sku_id"], "FIRST")
        self.assertEqual(
            {item["sku_id"] for item in turn["decision_result"]["ranked_candidates"]},
            {"FIRST", "SECOND"},
        )


if __name__ == "__main__":
    unittest.main()
