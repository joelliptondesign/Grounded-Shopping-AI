"""Streaming must be a delivery change only, never a rendering change."""

import unittest

from api.blocks import turn_to_blocks
from api.turn_stream import split_turn_payload


def _recommendation_turn():
    return {
        "intent": "recommend",
        "preference_state": {
            "hard_constraints": {"size": "queen"},
            "soft_preferences": {"budget_target": 1400},
            "priorities": {"cooling": "critical"},
            "recent_product_names": ["Polar Motion Elite"],
        },
        "decision_result": {
            "decision": "ALLOW",
            "ranked_candidates": [
                {"sku_id": "S02", "name": "Polar Motion Elite", "price": 1479, "cooling": 9,
                 "motion_isolation": 9, "support": 8, "firmness": 6},
                {"sku_id": "S05", "name": "Summit Chill Pro", "price": 1449, "cooling": 9,
                 "motion_isolation": 8, "support": 8, "firmness": 7},
            ],
        },
        "presentation": {
            "modality": "recommendation_cards",
            "message": "deterministic framing",
            "products": [
                {"sku_id": "S02", "name": "Polar Motion Elite", "price": 1479,
                 "why_it_matches": ["Strong overall fit", "Cooling: 9/10"], "tradeoff": ""},
                {"sku_id": "S05", "name": "Summit Chill Pro", "price": 1449,
                 "why_it_matches": ["Good value"], "tradeoff": "Higher-priced option"},
            ],
            "suggested_replies": [],
            "elicitation": None,
        },
    }


def _comparison_turn():
    return {
        "intent": "compare",
        "preference_state": {"recent_product_names": ["A", "B"]},
        "presentation": {
            "modality": "comparison_table",
            "products": [{"sku_id": "S02", "name": "Polar Motion Elite"},
                         {"sku_id": "S05", "name": "Summit Chill Pro"}],
            "comparison": {
                "products": ["Polar Motion Elite", "Summit Chill Pro"],
                "rows": [{"label": "Cooling", "values": ["9/10", "9/10"]},
                         {"label": "Price", "values": ["$1,479", "$1,449"]}],
            },
            "suggested_replies": [],
            "elicitation": None,
        },
    }


def _conversation_turn():
    return {
        "intent": "product_question",
        "preference_state": {"recent_product_names": ["Polar Motion Elite"]},
        "presentation": {
            "modality": "conversation",
            "products": [],
            "suggested_replies": [],
            "elicitation": None,
        },
    }


class TurnStreamTests(unittest.TestCase):
    """The streamed pieces must reassemble into the buffered payload exactly."""

    def _assert_equivalent(self, turn, message):
        buffered = turn_to_blocks(turn, message)
        structure, products, text_block, replies = split_turn_payload(turn, message)

        reassembled = []
        if text_block:
            reassembled.append(text_block)
        reassembled.extend(structure)
        if replies:
            reassembled.append({"kind": "suggest", "items": replies})

        self.assertEqual(reassembled, buffered["blocks"])
        self.assertEqual(products, buffered["products"])
        self.assertEqual(replies, buffered["replies"])

    def test_recommendation_blocks_are_unchanged_by_streaming(self):
        self._assert_equivalent(_recommendation_turn(), "Here are three options.")

    def test_comparison_blocks_are_unchanged_by_streaming(self):
        self._assert_equivalent(_comparison_turn(), "Here is the side-by-side.")

    def test_conversational_turn_streams_prose_and_pills_only(self):
        turn = _conversation_turn()
        structure, products, text_block, _replies = split_turn_payload(turn, "Cooling is 9/10.")
        self.assertEqual(structure, [])
        self.assertEqual(products, [])
        self.assertEqual(text_block["kind"], "text")
        self._assert_equivalent(turn, "Cooling is 9/10.")

    def test_structured_half_carries_no_prose_and_no_pills(self):
        """What renders early must never include the message or the pills."""
        for turn in (_recommendation_turn(), _comparison_turn()):
            structure, _products, text_block, _replies = split_turn_payload(turn, "framing")
            kinds = {block["kind"] for block in structure}
            self.assertNotIn("suggest", kinds)
            self.assertNotIn(text_block, structure)
            self.assertTrue(kinds)

    def test_service_discovery_heading_travels_with_its_cards(self):
        """The prototype introduces the alternatives with a bold heading."""
        turn = _recommendation_turn()
        turn["service_discovery"] = {"service": "haul_away", "region": "CA"}
        turn["presentation"]["heading"] = "Options with haul-away"
        turn["presentation"]["message"] = "These options don't include haul-away."

        structure, _products, text_block, _replies = split_turn_payload(turn, "framing")
        self.assertEqual(structure[0], {"kind": "text", "parts": [{"t": "Options with haul-away", "b": True}]})
        self.assertEqual(structure[1]["kind"], "recs")
        self.assertNotIn(text_block, structure)
        self._assert_equivalent(turn, "framing")

    def test_structured_half_does_not_depend_on_the_prose(self):
        """Cards sent before generation must equal the cards sent after it."""
        turn = _recommendation_turn()
        early, early_products, _t, _r = split_turn_payload(turn, None)
        late, late_products, _t2, _r2 = split_turn_payload(turn, "Some generated framing.")
        self.assertEqual(early, late)
        self.assertEqual(early_products, late_products)


if __name__ == "__main__":
    unittest.main()
