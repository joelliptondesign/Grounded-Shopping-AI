import unittest

from engine.data import SKU_CATALOG
from engine.decision import (
    DEFAULT_RANKING_WEIGHTS,
    evaluate_decision,
    normalized_ranking_weights,
    rank_skus,
    score_sku,
    semantic_priority_weight,
)


def sku(
    sku_id,
    *,
    price=1000,
    sizes=None,
    contains_latex=False,
    haul_away=True,
    firmness=6,
    support=7,
    cooling=8,
    motion_isolation=8,
):
    return {
        "sku_id": sku_id,
        "name": sku_id,
        "price": price,
        "available_sizes": sizes if sizes is not None else ["queen"],
        "contains_latex": contains_latex,
        "haul_away_CA_available": haul_away,
        "firmness": firmness,
        "support": support,
        "cooling": cooling,
        "motion_isolation": motion_isolation,
    }


class DecisionConstraintTests(unittest.TestCase):
    def test_semantic_priorities_map_to_deterministic_numeric_weights(self):
        self.assertEqual(semantic_priority_weight("low"), 1.0)
        self.assertEqual(semantic_priority_weight("medium"), 2.0)
        self.assertEqual(semantic_priority_weight("high"), 3.0)
        self.assertEqual(semantic_priority_weight("critical"), 4.0)

    def test_normalized_weights_sum_to_one(self):
        weights = normalized_ranking_weights(
            {"priorities": {"price": "low", "cooling": "critical"}}
        )
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertGreater(weights["cooling"], weights["price"])

    def test_default_weights_preserve_phase_two_fixed_weight_scorer(self):
        self.assertEqual(normalized_ranking_weights({}), DEFAULT_RANKING_WEIGHTS)

    def test_requested_size_available_remains_eligible(self):
        catalog = [sku("S1", sizes=["queen", "king"])]
        result = evaluate_decision({"requested_size": "king"}, catalog)
        self.assertEqual(result["decision"], "ALLOW")
        self.assertEqual(result["selected_sku"]["sku_id"], "S1")

    def test_requested_size_unavailable_is_excluded(self):
        catalog = [
            sku("S1", sizes=["queen"]),
            sku("S2", sizes=["king"]),
        ]
        result = evaluate_decision({"requested_size": "king"}, catalog)
        self.assertEqual([item["sku_id"] for item in result["ranked_candidates"]], ["S2"])
        self.assertEqual(
            result["metadata"]["excluded_candidates"],
            [{"sku_id": "S1", "violations": ["size_constraint"]}],
        )

    def test_no_sku_supports_requested_size_returns_no_match(self):
        result = evaluate_decision(
            {"requested_size": "cal_king"},
            [sku("S1", sizes=["queen"]), sku("S2", sizes=["king"])],
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["reason"], "no_valid_sku")
        self.assertEqual(result["violations"], ["size_constraint"])
        self.assertEqual(result["metadata"]["candidate_count"], 0)

    def test_hard_max_price_excludes_over_budget_products(self):
        catalog = [sku("S1", price=2400), sku("S2", price=2399)]
        result = evaluate_decision({"max_price": 2399}, catalog)
        self.assertEqual([item["sku_id"] for item in result["ranked_candidates"]], ["S2"])

    def test_soft_budget_target_is_not_a_hard_ceiling(self):
        catalog = [sku("S1", price=2000)]
        result = evaluate_decision({"budget_target": 1000}, catalog)
        self.assertEqual(result["decision"], "ALLOW")
        self.assertEqual(result["selected_sku"]["sku_id"], "S1")

    def test_latex_exclusion_uses_structured_state_not_raw_text(self):
        catalog = [sku("S1", contains_latex=True)]
        raw_text_only = evaluate_decision(
            {"query_text": "I am allergic to latex"},
            catalog,
        )
        structured = evaluate_decision({"exclude_latex": True}, catalog)
        self.assertEqual(raw_text_only["decision"], "ALLOW")
        self.assertEqual(structured["decision"], "BLOCK")
        self.assertEqual(structured["violations"], ["latex_constraint"])

    def test_haul_away_requirement_excludes_ineligible_products(self):
        catalog = [sku("S1", haul_away=False), sku("S2", haul_away=True)]
        result = evaluate_decision({"require_CA_haul_away": True}, catalog)
        self.assertEqual([item["sku_id"] for item in result["ranked_candidates"]], ["S2"])

    def test_multiple_hard_constraints_combine(self):
        catalog = [
            sku("S1", price=2500, sizes=["queen"], contains_latex=True, haul_away=False),
            sku("S2", price=2000, sizes=["king"], contains_latex=False, haul_away=True),
            sku("S3", price=2000, sizes=["king"], contains_latex=False, haul_away=False),
        ]
        preferences = {
            "requested_size": "king",
            "max_price": 2400,
            "exclude_latex": True,
            "require_CA_haul_away": True,
        }
        result = evaluate_decision(preferences, catalog)
        self.assertEqual([item["sku_id"] for item in result["ranked_candidates"]], ["S2"])
        s1 = result["metadata"]["excluded_candidates"][0]
        self.assertEqual(
            s1["violations"],
            ["size_constraint", "max_price", "latex_constraint", "require_CA_haul_away"],
        )

    def test_existing_fixed_weight_ranking_is_unchanged(self):
        preferences = {
            "firmness_preference": 6,
            "support_preference": 8,
            "cooling_preference": 8,
            "motion_isolation_preference": 8,
        }
        expected = sorted(
            SKU_CATALOG,
            key=lambda item: (-score_sku(preferences, item), item["sku_id"]),
        )
        self.assertEqual(
            [item["sku_id"] for item in rank_skus(preferences, SKU_CATALOG)],
            [item["sku_id"] for item in expected],
        )

    def test_cooling_medium_to_critical_can_change_winner(self):
        catalog = [
            sku(
                "COOL",
                firmness=9,
                support=9,
                cooling=10,
                motion_isolation=9,
            ),
            sku(
                "BALANCED",
                firmness=10,
                support=10,
                cooling=7,
                motion_isolation=10,
            ),
        ]
        base = {
            "firmness_preference": 10,
            "support_preference": 10,
            "cooling_preference": 10,
            "motion_isolation_preference": 10,
        }
        medium = evaluate_decision(
            {**base, "priorities": {"cooling": "medium"}}, catalog
        )
        critical = evaluate_decision(
            {**base, "priorities": {"cooling": "critical"}},
            catalog,
            previous_decision_result=medium,
        )
        self.assertEqual(medium["selected_sku"]["sku_id"], "BALANCED")
        self.assertEqual(critical["selected_sku"]["sku_id"], "COOL")
        cool_score = critical["metadata"]["candidate_scores"][0]
        self.assertEqual(cool_score["previous_rank"], 2)
        self.assertEqual(cool_score["current_rank"], 1)

    def test_motion_priority_can_change_winner(self):
        catalog = [
            sku(
                "MOTION",
                firmness=9,
                support=9,
                cooling=9,
                motion_isolation=10,
            ),
            sku(
                "BALANCED",
                firmness=10,
                support=10,
                cooling=10,
                motion_isolation=7,
            ),
        ]
        base = {
            "firmness_preference": 10,
            "support_preference": 10,
            "cooling_preference": 10,
            "motion_isolation_preference": 10,
        }
        medium = evaluate_decision(
            {**base, "priorities": {"motion_isolation": "medium"}}, catalog
        )
        critical = evaluate_decision(
            {**base, "priorities": {"motion_isolation": "critical"}}, catalog
        )
        self.assertEqual(medium["selected_sku"]["sku_id"], "BALANCED")
        self.assertEqual(critical["selected_sku"]["sku_id"], "MOTION")

    def test_price_priority_does_not_change_max_price_eligibility(self):
        catalog = [sku("UNDER", price=1500), sku("OVER", price=2500)]
        low = evaluate_decision(
            {"max_price": 2400, "priorities": {"price": "low"}}, catalog
        )
        critical = evaluate_decision(
            {"max_price": 2400, "priorities": {"price": "critical"}}, catalog
        )
        self.assertEqual(
            [item["sku_id"] for item in low["ranked_candidates"]], ["UNDER"]
        )
        self.assertEqual(
            [item["sku_id"] for item in critical["ranked_candidates"]], ["UNDER"]
        )
        self.assertEqual(
            low["metadata"]["active_hard_constraints"],
            critical["metadata"]["active_hard_constraints"],
        )

    def test_identical_inputs_have_deterministic_rank_order(self):
        preferences = {
            "cooling_preference": 9,
            "priorities": {"cooling": "critical", "price": "low"},
        }
        first = evaluate_decision(preferences, SKU_CATALOG)
        second = evaluate_decision(preferences, SKU_CATALOG)
        self.assertEqual(
            [item["sku_id"] for item in first["ranked_candidates"]],
            [item["sku_id"] for item in second["ranked_candidates"]],
        )
        self.assertEqual(
            first["metadata"]["candidate_scores"],
            second["metadata"]["candidate_scores"],
        )


if __name__ == "__main__":
    unittest.main()
