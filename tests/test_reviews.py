import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response
from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision
from engine.grounding import validate_review_text
from engine.preference_extraction import EMPTY_STATE, INTENTS
from engine.review_data import REVIEW_FIXTURE_SOURCE, review_slice


def extracted(intent="product_question", *, products=None, source="reviews", topic="general", cooling_priority=None):
    return {
        "intent": intent,
        "turn_context": {
            "product_names": products or [],
            "product_attribute": None,
            "service_attribute": None,
            "exact_product_request": False,
            "information_source": source,
            "review_topic": topic,
        },
        "recovery_response": "none",
        "hard_constraints": {"size": None, "max_price": None, "exclude_latex": None, "require_CA_haul_away": None},
        "soft_preferences": {"budget_target": None, "firmness_target": None, "support_target": None, "cooling_target": None, "motion_isolation_target": None},
        "priorities": {"price": None, "firmness": None, "support": None, "cooling": cooling_priority, "motion_isolation": None},
        "needs_clarification": False,
        "clarification_question": None,
    }


class FakeClient:
    def __init__(self, output):
        self.output = output
        self.responses = self

    def create(self, **kwargs):
        value = self.output.pop(0) if isinstance(self.output, list) else self.output
        return SimpleNamespace(output_text=value if isinstance(value, str) else json.dumps(value))


class ReviewEvidenceTests(unittest.TestCase):
    def turn(self, message, update, state=None, previous=None):
        return process_conversation_turn(
            message,
            deepcopy(state or EMPTY_STATE),
            SKU_CATALOG,
            client=FakeClient(update),
            previous_decision_result=previous,
        )

    def test_review_questions_extend_context_not_primary_taxonomy(self):
        self.assertEqual(INTENTS, ("recommend", "compare", "product_question", "service_question", "off_topic"))
        turn = self.turn("What do people say about Metro Cool Comfort?", extracted(products=["Metro Cool Comfort"]))
        self.assertEqual(turn["intent"], "product_question")
        self.assertEqual(turn["response_strategy"], "review_evidence_lookup")

    def test_general_question_uses_structured_fixture(self):
        turn = self.turn("What do people say about Metro Cool Comfort?", extracted(products=["Metro Cool Comfort"]))
        self.assertEqual(turn["grounding_data"]["authoritative_source"], REVIEW_FIXTURE_SOURCE)
        self.assertIn("sleeping cooler", turn["response_text"].casefold())
        self.assertEqual(turn["modality"], "conversation")

    def test_specific_cooling_question_is_narrow(self):
        turn = self.turn("Do people think it sleeps hot?", extracted(products=["Metro Cool Comfort"], topic="cooling"))
        record = turn["grounding_data"]["records"][0]
        self.assertEqual(set(record["themes"]), {"cooling"})
        self.assertNotIn("common_complaints", record)
        self.assertIn("cooler", turn["response_text"].casefold())

    def test_complaint_question_uses_only_represented_complaints(self):
        turn = self.turn("What don't people like about it?", extracted(products=["Metro Cool Comfort"], topic="complaints"))
        self.assertIn("firmer", turn["response_text"].casefold())
        self.assertNotIn("themes", turn["grounding_data"]["records"][0])

    def test_unknown_review_topic_stays_unknown(self):
        turn = self.turn("What do reviews say about edge support?", extracted(products=["Metro Cool Comfort"], topic="edge_support"))
        self.assertTrue(turn["grounding_data"]["unknown_topics"])
        self.assertIn("don't have enough review information", turn["response_text"])

    def test_catalog_attribute_is_not_review_evidence(self):
        turn = self.turn("What is its cooling score?", extracted(products=["Metro Cool Comfort"], source="catalog", topic=None))
        self.assertEqual(turn["response_strategy"], "catalog_fact_lookup")
        self.assertNotIn("records", turn["grounding_data"])

    def test_catalog_review_disagreement_preserves_both(self):
        turn = self.turn("How firm do owners find it?", extracted(products=["Metro Cool Comfort"], topic="firmness"))
        self.assertEqual(turn["grounding_data"]["catalog_context"][0]["firmness"], 6)
        self.assertIn("listed at 6/10", turn["response_text"])
        self.assertIn("firmer than expected", turn["response_text"])

    def test_reviews_do_not_change_eligibility_or_ranking(self):
        prefs = {"requested_size": "queen", "max_price": 1500, "cooling_preference": 9, "priorities": {"cooling": "critical"}}
        before = evaluate_decision(prefs, SKU_CATALOG)
        review_slice([item["sku_id"] for item in SKU_CATALOG], "cooling")
        after = evaluate_decision(prefs, SKU_CATALOG)
        self.assertEqual(before["selected_sku"]["sku_id"], after["selected_sku"]["sku_id"])
        self.assertEqual(before["metadata"]["candidate_scores"], after["metadata"]["candidate_scores"])
        self.assertEqual([x["sku_id"] for x in before["ranked_candidates"]], [x["sku_id"] for x in after["ranked_candidates"]])

    def test_review_evidence_cannot_override_hard_fact(self):
        fact = next(item for item in SKU_CATALOG if item["sku_id"] == "S06")
        self.assertFalse(fact["contains_latex"])
        self.assertNotIn("contains_latex", review_slice(["S06"], "general")["records"][0])

    def test_recommendation_may_enrich_card_after_ranking(self):
        update = extracted("recommend", source=None, topic=None, cooling_priority="critical")
        turn = self.turn("Cooling matters most. Recommend one.", update)
        selected = turn["decision_result"]["selected_sku"]["sku_id"]
        self.assertEqual(turn["presentation"]["products"][0]["sku_id"], selected)
        self.assertTrue(turn["review_debug"]["appeared_in_cards"])
        self.assertFalse(turn["grounding_evidence"]["review_evidence_is_ranking_input"])

    def test_recommendation_explanation_may_use_supplied_review_theme(self):
        turn = self.turn(
            "Cooling matters most. Recommend one.",
            extracted("recommend", source=None, topic=None, cooling_priority="critical"),
        )
        name = turn["decision_result"]["selected_sku"]["name"]
        summary = turn["grounding_evidence"]["review_evidence"]["records"][0]["themes"]["cooling"]["summary"]
        response = generate_turn_response(
            turn,
            "Cooling matters most. Recommend one.",
            catalog=SKU_CATALOG,
            client=FakeClient(f"I'd start with {name}. Review feedback supports the fit: {summary}"),
        )
        self.assertIn(summary, response)
        self.assertTrue(turn["review_debug"]["appeared_in_explanation"])

    def test_irrelevant_reviews_are_not_added_to_recommendation(self):
        turn = self.turn("Recommend a mattress.", extracted("recommend", source=None, topic=None))
        self.assertNotIn("review_evidence", turn["grounding_evidence"])
        self.assertFalse(turn["review_debug"]["appeared_in_cards"])

    def test_review_comparison_adds_relevant_human_row(self):
        turn = self.turn("What do reviews say about these two for cooling?", extracted("compare", products=["Metro Cool Comfort", "Urban Rest Core"], topic="cooling"))
        rows = turn["presentation"]["comparison"]["rows"]
        self.assertEqual(rows[0]["key"], "review_cooling")
        self.assertEqual(rows[0]["source"], REVIEW_FIXTURE_SOURCE)
        self.assertTrue(turn["review_debug"]["appeared_in_comparison"])

    def test_model_cannot_invent_theme_rating_count_or_quote(self):
        evidence = review_slice(["S06"], "cooling")
        cases = {
            "Reviewers love the edge support.": "unrepresented_review_theme:edge_support",
            "It has 999 reviews.": "unverified_review_count",
            "It is rated 4.9 stars.": "unverified_average_rating",
            'One reviewer said, "Perfect mattress."': "unsupported_verbatim_review_quote",
            "Customers say it contains latex.": "unrepresented_catalog_claim:contains_latex",
            "It is currently rated 4.4 stars.": "unsupported_live_review_claim",
        }
        for text, reason in cases.items():
            with self.subTest(text=text):
                self.assertIn(reason, validate_review_text(text, evidence)["reasons"])

    def test_product_name_does_not_create_an_unrepresented_review_topic(self):
        evidence = review_slice(["S06"], "firmness")
        evidence["catalog_context"] = [
            {"name": "Metro Cool Comfort", "firmness": 6}
        ]
        result = validate_review_text(
            "Owners describe Metro Cool Comfort as medium-firm; it is listed at 6/10.",
            evidence,
        )
        self.assertTrue(result["valid"], result["reasons"])

    def test_review_pronoun_can_use_previous_selected_product(self):
        recommendation = self.turn("Recommend one.", extracted("recommend", source=None, topic=None))
        turn = self.turn(
            "What do people say about this one?",
            extracted(products=[], topic="general"),
            previous=recommendation["decision_result"],
        )
        self.assertEqual(
            turn["grounding_data"]["records"][0]["sku_id"],
            recommendation["decision_result"]["selected_sku"]["sku_id"],
        )

    def test_invalid_generated_review_claim_retries_to_grounded_answer(self):
        turn = self.turn("How is edge support in reviews?", extracted(products=["Metro Cool Comfort"], topic="edge_support"))
        client = FakeClient(["Reviewers love the edge support.", "I don't have enough review information about edge support for Metro Cool Comfort."])
        audit = {}
        response = generate_turn_response(turn, "How is edge support in reviews?", catalog=SKU_CATALOG, client=client, audit=audit)
        self.assertIn("don't have enough", response)
        self.assertEqual(len(audit["attempts"]), 2)


if __name__ == "__main__":
    unittest.main()
