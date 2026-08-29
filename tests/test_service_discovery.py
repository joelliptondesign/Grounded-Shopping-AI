"""A haul-away question about a shortlist is a service need, not just a fact."""

import json
import unittest
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.data import SKU_CATALOG
from engine.preference_extraction import new_preference_state


BY_ID = {sku["sku_id"]: sku for sku in SKU_CATALOG}
NO_SERVICE = [sku for sku in SKU_CATALOG if sku.get("haul_away_CA_available") is not True]
WITH_SERVICE = [sku for sku in SKU_CATALOG if sku.get("haul_away_CA_available") is True]


class Client:
    def __init__(self, result):
        self.result = result
        self.responses = self

    def create(self, **kwargs):
        return SimpleNamespace(output_text=json.dumps(self.result))


def service_update(product_names):
    return {
        "intent": "service_question",
        "shopping_action": {
            "action": "answer_service_question",
            "product_ids": list(product_names),
            "product_attribute": None,
            "service_attribute": "haul_away",
        },
        "turn_context": {
            "product_names": list(product_names),
            "product_attribute": None,
            "service_attribute": "haul_away",
            "exact_product_request": False,
            "information_source": None,
            "review_topic": None,
            "explicit_browse_intent": False,
        },
        "recovery_response": "none",
        "hard_constraints": {"size": None, "max_price": None, "exclude_latex": None,
                             "require_CA_haul_away": None},
        "soft_preferences": {"budget_target": None, "budget_flex_max": None,
                             "prefer_CA_haul_away": None, "firmness_target": None,
                             "support_target": None, "cooling_target": None,
                             "motion_isolation_target": None},
        "directions": {"price": None, "firmness": None, "support": None,
                       "cooling": None, "motion_isolation": None},
        "priorities": {"price": None, "firmness": None, "support": None,
                       "cooling": None, "motion_isolation": None},
        "needs_clarification": False,
        "clarification_question": None,
        "clarification_reason": None,
        "recommendation_readiness": "exploratory",
    }


def shopper(shown, *, size="twin", budget=700, cooling=None):
    state = new_preference_state()
    state["hard_constraints"]["size"] = size
    state["soft_preferences"]["budget_target"] = budget
    if cooling:
        state["priorities"]["cooling"] = cooling
    state["recent_product_names"] = [BY_ID[sku]["name"] for sku in shown]
    state["recent_presentations"] = [{
        "modality": "recommendation_cards",
        "product_ids": list(shown),
        "product_names": [BY_ID[sku]["name"] for sku in shown],
        "action": "recommend_products",
        "product_attribute": None,
        "service_attribute": None,
        "information_source": None,
        "review_topic": None,
    }]
    return state


def turn(message, shown, **kwargs):
    state = shopper(shown, **kwargs)
    names = [BY_ID[sku]["name"] for sku in shown]
    return process_conversation_turn(
        message, state, SKU_CATALOG, client=Client(service_update(names))
    )


class ServiceDiscoveryTests(unittest.TestCase):
    def _shortlist_without_service(self, size="twin"):
        return [
            sku["sku_id"]
            for sku in NO_SERVICE
            if size in sku.get("available_sizes", [])
        ][:2]

    def test_no_shown_product_has_haul_away_so_alternatives_are_offered(self):
        shown = self._shortlist_without_service()
        result = turn("Does either include haul-away?", shown)

        self.assertEqual(result["response_strategy"], "service_discovery")
        self.assertEqual(result["modality"], "recommendation_cards")
        self.assertEqual(result["presentation"]["heading"], "Options with haul-away")

        offered = [card["sku_id"] for card in result["presentation"]["products"]]
        self.assertTrue(offered)
        self.assertTrue(all(BY_ID[sku]["haul_away_CA_available"] is True for sku in offered))
        self.assertFalse(set(offered) & set(shown), "already-shown products are not re-offered")

    def test_alternatives_keep_the_shopper_state(self):
        """Size, budget and priorities survive the service search."""
        shown = self._shortlist_without_service(size="queen")
        result = turn("How do I get rid of my old mattress?", shown,
                      size="queen", budget=1400, cooling="critical")

        offered = [card["sku_id"] for card in result["presentation"]["products"]]
        self.assertTrue(offered)
        for sku in offered:
            self.assertIn("queen", BY_ID[sku]["available_sizes"])
            self.assertTrue(BY_ID[sku]["haul_away_CA_available"])

    def test_service_requirement_is_not_made_permanent(self):
        """The search applies the requirement; the shopper's state keeps its own."""
        shown = self._shortlist_without_service()
        result = turn("Does either include haul-away?", shown)
        self.assertIsNone(
            result["preference_state"]["hard_constraints"].get("require_CA_haul_away")
        )

    def test_a_shown_product_with_haul_away_stays_a_direct_answer(self):
        shown = [WITH_SERVICE[0]["sku_id"], NO_SERVICE[0]["sku_id"]]
        result = turn("Does either include haul-away?", shown)
        self.assertNotEqual(result["response_strategy"], "service_discovery")
        self.assertEqual(result["modality"], "conversation")

    def test_naming_one_product_stays_a_narrow_fact(self):
        shown = self._shortlist_without_service()
        named = BY_ID[shown[0]]["name"]
        result = turn(f"Does {named} include haul-away?", shown)
        self.assertNotEqual(result["response_strategy"], "service_discovery")
        self.assertEqual(result["modality"], "conversation")

    def test_availability_covers_every_referenced_product(self):
        shown = self._shortlist_without_service()
        result = turn("Does either include haul-away?", shown)
        availability = result["service_availability"]
        self.assertEqual(len(availability["products"]), len(shown))
        self.assertFalse(availability["any_available"])

    def test_message_explains_the_gap_before_the_alternatives(self):
        shown = self._shortlist_without_service()
        result = turn("Does either include haul-away?", shown)
        message = result["presentation"]["message"].casefold()
        self.assertIn("haul-away", message)
        self.assertIn("don't include", message)


if __name__ == "__main__":
    unittest.main()
