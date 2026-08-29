import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.data import SKU_CATALOG
from engine.preference_extraction import new_preference_state
from engine.presentation import MODALITIES, _card_tradeoff


def extracted(
    intent="recommend",
    *,
    products=None,
    attribute=None,
    size=None,
    max_price=None,
    haul_away=None,
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
            "product_attribute": attribute,
            "service_attribute": None,
            "exact_product_request": False,
        },
        "recovery_response": recovery_response,
        "hard_constraints": {
            "size": size,
            "max_price": max_price,
            "exclude_latex": None,
            "require_CA_haul_away": haul_away,
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
        "needs_clarification": clarification,
        "clarification_question": question,
    }


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.responses = self

    def create(self, **kwargs):
        return SimpleNamespace(output_text=json.dumps(self.result))


class AdaptivePresentationTests(unittest.TestCase):
    def turn(self, message, update, state=None, previous=None, catalog=None):
        return process_conversation_turn(
            message,
            deepcopy(state) if state is not None else new_preference_state(),
            catalog or SKU_CATALOG,
            client=FakeClient(update),
            previous_decision_result=previous,
        )

    def test_taxonomy_and_contract_are_small_and_explicit(self):
        self.assertEqual(
            MODALITIES,
            (
                "conversation",
                "recommendation_cards",
                "comparison_table",
                "product_detail",
                "recovery_choices",
            ),
        )
        turn = self.turn(
            "Does Metro Cool Comfort contain latex?",
            extracted(
                "product_question",
                products=["Metro Cool Comfort"],
                attribute="contains_latex",
            ),
        )
        self.assertEqual(
            set(turn["presentation"]),
            {
                "modality",
                "message",
                "products",
                "comparison",
                "actions",
                "suggested_replies",
                "elicitation",
                "selection_reason",
                "grounding_sources",
            },
        )
        self.assertEqual(turn["modality"], turn["presentation"]["modality"])

    def test_simple_factual_answer_stays_conversational(self):
        turn = self.turn(
            "Does Metro Cool Comfort contain latex?",
            extracted(
                "product_question",
                products=["Metro Cool Comfort"],
                attribute="contains_latex",
            ),
        )
        self.assertEqual(turn["modality"], "conversation")
        self.assertEqual(turn["presentation"]["products"], [])
        self.assertIn("not containing latex", turn["presentation"]["message"])

    def test_recommendation_cards_preserve_rank_and_grounded_claims(self):
        turn = self.turn(
            "Find me a cool king under $2,000.",
            extracted(
                size="king",
                max_price=2000,
                cooling=9,
                cooling_priority="critical",
            ),
        )
        presentation = turn["presentation"]
        self.assertEqual(presentation["modality"], "recommendation_cards")
        ranked_ids = [
            product["sku_id"]
            for product in turn["decision_result"]["ranked_candidates"][:3]
        ]
        card_ids = [product["sku_id"] for product in presentation["products"]]
        self.assertEqual(card_ids, ranked_ids)

        catalog_by_id = {product["sku_id"]: product for product in SKU_CATALOG}
        for card in presentation["products"]:
            source = catalog_by_id[card["sku_id"]]
            self.assertEqual(card["name"], source["name"])
            self.assertEqual(card["price"], source["price"])
            self.assertTrue(all("9/10" not in reason or source["cooling"] == 9 for reason in card["why_it_matches"]))
        self.assertEqual(
            presentation["grounding_sources"]["ordering"],
            "validated_shopping_agent_selection",
        )

    def test_card_tradeoffs_use_concise_shopper_language(self):
        state = new_preference_state()
        state["soft_preferences"]["cooling_target"] = 9
        state["priorities"]["cooling"] = "critical"
        displayed = [
            {"price": 1500, "cooling": 9},
            {"price": 1000, "cooling": 8},
        ]

        self.assertEqual(
            _card_tradeoff(displayed[0], displayed, state),
            "Higher-priced option",
        )
        self.assertEqual(
            _card_tradeoff(displayed[1], displayed, state),
            "Slightly lower cooling",
        )

    def test_comparison_rows_use_catalog_and_prioritize_context(self):
        state = new_preference_state()
        state["hard_constraints"]["size"] = "king"
        state["soft_preferences"]["cooling_target"] = 9
        state["priorities"]["cooling"] = "critical"
        turn = self.turn(
            "Compare Metro Cool Comfort and Urban Rest Core.",
            extracted(
                "compare", products=["Metro Cool Comfort", "Urban Rest Core"]
            ),
            state,
        )
        comparison = turn["presentation"]["comparison"]
        self.assertEqual(turn["modality"], "comparison_table")
        self.assertEqual(comparison["rows"][0]["key"], "cooling")
        cooling = comparison["rows"][0]
        self.assertEqual(cooling["values"], ["7/10", "6/10"])
        self.assertEqual(cooling["source"], "structured_catalog_fixture")
        self.assertNotIn("sku_id", [row["key"] for row in comparison["rows"]])

    def test_information_rich_product_request_uses_product_detail(self):
        turn = self.turn(
            "Tell me more about Metro Cool Comfort.",
            extracted("product_question", products=["Metro Cool Comfort"]),
        )
        self.assertEqual(turn["modality"], "product_detail")
        detail = turn["presentation"]["products"][0]
        self.assertEqual(detail["sku_id"], "S06")
        keys = [item["key"] for item in detail["details"]]
        self.assertIn("materials", keys)
        self.assertIn("available_sizes", keys)
        self.assertIn("haul_away_CA_available", keys)
        service = next(
            item for item in detail["details"] if item["key"] == "haul_away_CA_available"
        )
        self.assertEqual(
            service["source"], "structured_service_fixture_and_eligibility_logic"
        )

    def test_no_match_uses_evidence_backed_recovery_choices(self):
        turn = self.turn(
            "I need a king under $200 with California haul-away.",
            extracted(size="king", max_price=200, haul_away=True),
        )
        presentation = turn["presentation"]
        self.assertEqual(presentation["modality"], "recovery_choices")
        proposal = turn["recovery"]["proposed_relaxation"]
        approve = presentation["actions"][0]
        self.assertEqual(approve["patch"], proposal["state_patch"])
        self.assertEqual(approve["match_count"], proposal["match_count"])
        self.assertEqual(approve["action"], "approve_relaxation")
        self.assertEqual(
            presentation["actions"][-1]["action"], "reject_relaxation"
        )
        self.assertEqual(
            turn["preference_state"]["hard_constraints"]["max_price"], 200
        )
        self.assertTrue(turn["recovery"]["requires_user_approval"])
        self.assertTrue(presentation["suggested_replies"])

    def test_clarification_stays_conversational_with_useful_replies(self):
        question = "What bothers you most about your current mattress?"
        turn = self.turn(
            "I don't want it to feel like my current mattress.",
            extracted(clarification=True, question=question),
        )
        self.assertEqual(turn["modality"], "conversation")
        self.assertIn("It sleeps too hot", turn["presentation"]["suggested_replies"])
        self.assertIsNone(turn["decision_result"])

    def test_preference_state_survives_modality_changes(self):
        first = self.turn(
            "King around $2,000, and cooling matters most.",
            extracted(size="king", cooling=9, cooling_priority="critical"),
        )
        names = [
            product["name"]
            for product in first["decision_result"]["ranked_candidates"][:2]
        ]
        second = self.turn(
            "Compare the first two.",
            extracted("compare", products=names),
            first["preference_state"],
            first["decision_result"],
        )
        third = self.turn(
            f"Does {names[0]} contain latex?",
            extracted(
                "product_question", products=[names[0]], attribute="contains_latex"
            ),
            second["preference_state"],
            first["decision_result"],
        )
        self.assertEqual(
            [first["modality"], second["modality"], third["modality"]],
            ["recommendation_cards", "comparison_table", "conversation"],
        )
        self.assertEqual(
            third["preference_state"]["hard_constraints"]["size"], "king"
        )
        self.assertEqual(
            third["preference_state"]["priorities"]["cooling"], "critical"
        )

    def test_fixture_runs_end_to_end_across_four_modalities(self):
        fixture_path = (
            Path(__file__).resolve().parent.parent
            / "fixtures"
            / "adaptive_modality.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        state = new_preference_state()
        previous = None

        first = self.turn(
            fixture["turns"][0]["shopper"],
            extracted(size="king", cooling=9, cooling_priority="critical"),
            state,
            previous,
        )
        names = [item["name"] for item in first["decision_result"]["ranked_candidates"][:2]]
        second = self.turn(
            fixture["turns"][1]["shopper"],
            extracted("compare", products=names),
            first["preference_state"],
            first["decision_result"],
        )
        third = self.turn(
            fixture["turns"][2]["shopper"],
            extracted("product_question", products=[names[0]], attribute="contains_latex"),
            second["preference_state"],
            first["decision_result"],
        )
        fourth = self.turn(
            fixture["turns"][3]["shopper"],
            extracted(max_price=1000, haul_away=True),
            third["preference_state"],
            first["decision_result"],
        )
        self.assertEqual(
            [first["modality"], second["modality"], third["modality"], fourth["modality"]],
            [item["expected_modality"] for item in fixture["turns"]],
        )
        self.assertEqual(fourth["preference_state"]["hard_constraints"]["size"], "king")


if __name__ == "__main__":
    unittest.main()
