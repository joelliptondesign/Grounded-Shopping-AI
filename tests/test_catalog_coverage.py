import unittest

from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision, score_dimensions, score_sku
from engine.grounding import build_recommendation_evidence
from engine.presentation import _card_reasons
from engine.preference_extraction import new_preference_state
from engine.review_data import REVIEW_EVIDENCE
from engine.response_strategy import build_product_fact, build_service_fact


SUPPORTED_SIZES = {"twin", "twin_xl", "full", "queen", "king", "cal_king"}
SCORE_FIELDS = ("firmness", "support", "cooling", "motion_isolation")


class CatalogCoverageTests(unittest.TestCase):
    def test_catalog_identity_schema_and_unique_skus(self):
        self.assertGreaterEqual(len(SKU_CATALOG), 45)
        self.assertLessEqual(len(SKU_CATALOG), 50)
        ids = [product["sku_id"] for product in SKU_CATALOG]
        self.assertEqual(len(ids), len(set(ids)))
        for product in SKU_CATALOG:
            self.assertIsInstance(product["sku_id"], str)
            self.assertTrue(product["name"])
            self.assertGreater(product["price"], 0)
            self.assertTrue(product["available_sizes"])
            self.assertTrue(set(product["available_sizes"]).issubset(SUPPORTED_SIZES))
            self.assertTrue(product.get("materials"))
            for field in SCORE_FIELDS:
                value = product.get(field)
                self.assertTrue(value is None or 1 <= value <= 10)
            self.assertIn(product.get("contains_latex"), (True, False, None))
            self.assertIn(product.get("haul_away_CA_available"), (True, False, None))

    def test_price_and_size_coverage_is_broad(self):
        prices = [product["price"] for product in SKU_CATALOG]
        self.assertLessEqual(min(prices), 250)
        self.assertGreater(max(prices), 2500)
        bands = (
            (200, 400),
            (400, 700),
            (700, 1000),
            (1000, 1500),
            (1500, 2000),
            (2000, 2500),
            (2500, float("inf")),
        )
        self.assertTrue(all(any(low <= price < high for price in prices) for low, high in bands))
        self.assertGreaterEqual(sum("queen" in p["available_sizes"] for p in SKU_CATALOG), 40)
        self.assertGreaterEqual(sum("king" in p["available_sizes"] for p in SKU_CATALOG), 30)
        for size in SUPPORTED_SIZES:
            self.assertGreaterEqual(sum(size in p["available_sizes"] for p in SKU_CATALOG), 8)

    def test_trust_fields_cover_true_false_and_unknown(self):
        for field in ("contains_latex", "haul_away_CA_available"):
            values = [product.get(field) for product in SKU_CATALOG]
            self.assertIn(True, values)
            self.assertIn(False, values)
            self.assertIn(None, values)
        latex_free_prices = [p["price"] for p in SKU_CATALOG if p.get("contains_latex") is False]
        self.assertLess(min(latex_free_prices), 500)
        self.assertTrue(any(price >= 1500 for price in latex_free_prices))

    def test_common_scenarios_have_multiple_candidates(self):
        scenarios = {
            "under_500": lambda p: p["price"] < 500,
            "queen_under_700": lambda p: "queen" in p["available_sizes"] and p["price"] < 700,
            "king_under_1000": lambda p: "king" in p["available_sizes"] and p["price"] < 1000,
            "cooling_around_1000": lambda p: 700 <= p["price"] <= 1200 and (p.get("cooling") or 0) >= 8,
            "cooling_motion_around_1500": lambda p: 1200 <= p["price"] <= 1800 and (p.get("cooling") or 0) >= 8 and (p.get("motion_isolation") or 0) >= 8,
            "firm_support_around_1000": lambda p: 700 <= p["price"] <= 1300 and (p.get("firmness") or 0) >= 7 and (p.get("support") or 0) >= 8,
            "latex_free_under_1000": lambda p: p["price"] < 1000 and p.get("contains_latex") is False,
            "haul_away_under_1000": lambda p: p["price"] < 1000 and p.get("haul_away_CA_available") is True,
            "premium_cooling": lambda p: 1500 <= p["price"] <= 2500 and (p.get("cooling") or 0) >= 9,
        }
        for label, predicate in scenarios.items():
            with self.subTest(label=label):
                self.assertGreaterEqual(sum(predicate(product) for product in SKU_CATALOG), 2)

    def test_unknown_consequential_evidence_blocks_eligibility(self):
        unknown = {
            "sku_id": "UNKNOWN",
            "name": "Unknown",
            "price": 500,
            "available_sizes": None,
            "firmness": 6,
            "support": 6,
            "cooling": 6,
            "motion_isolation": 6,
            "contains_latex": None,
            "haul_away_CA_available": None,
        }
        result = evaluate_decision(
            {
                "requested_size": "king",
                "exclude_latex": True,
                "require_CA_haul_away": True,
            },
            [unknown],
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(
            set(result["violations"]),
            {
                "unknown_size_constraint",
                "unknown_latex_constraint",
                "unknown_require_CA_haul_away",
            },
        )

    def test_optional_unknown_score_is_none_and_not_zero(self):
        preferences = {
            "directions": {"cooling": "higher"},
            "priorities": {"cooling": "critical"},
        }
        unknown = {
            "price": 1000,
            "firmness": 7,
            "support": 7,
            "cooling": None,
            "motion_isolation": 7,
        }
        known_zero = {**unknown, "cooling": 0}
        self.assertIsNone(score_dimensions(preferences, unknown)["cooling"])
        self.assertGreater(score_sku(preferences, unknown), score_sku(preferences, known_zero))

    def test_null_fact_and_service_values_remain_unverified(self):
        product = {
            "sku_id": "NULLS",
            "name": "Sparse Product",
            "price": 500,
            "available_sizes": ["queen"],
            "cooling": None,
            "haul_away_CA_available": None,
        }
        self.assertFalse(build_product_fact(["NULLS"], "cooling", [product])["verified"])
        self.assertFalse(
            build_service_fact(
                ["NULLS"], [product], service_attribute="haul_away"
            )["verified"]
        )
        evidence = build_recommendation_evidence(
            {
                "decision": "ALLOW",
                "reason": "valid_recommendation",
                "selected_sku": product,
                "ranked_candidates": [product],
                "metadata": {},
            },
            {},
        )
        self.assertIn("cooling", evidence["fact_status"]["unknown_product_facts"])
        self.assertFalse(evidence["verified_services"]["CA_haul_away"]["verified"])

    def test_compact_card_omits_null_and_uses_represented_evidence(self):
        state = new_preference_state()
        state["priorities"].update(
            {"cooling": "critical", "motion_isolation": "high", "support": "medium"}
        )
        product = {"cooling": None, "motion_isolation": 8, "support": 7}
        reasons = _card_reasons(product, state)
        self.assertFalse(any("Unknown" in reason or "Cooling" in reason for reason in reasons))
        self.assertIn("Motion isolation: 8/10", reasons)
        self.assertIn("Support: 7/10", reasons)

    def test_reviews_cover_every_product_with_intentional_topic_variation(self):
        catalog_ids = {product["sku_id"] for product in SKU_CATALOG}
        self.assertEqual(catalog_ids, set(REVIEW_EVIDENCE))
        theme_counts = [len(record.get("themes", {})) for record in REVIEW_EVIDENCE.values()]
        self.assertGreater(max(theme_counts), min(theme_counts))
        self.assertTrue(any("common_praise" not in record for record in REVIEW_EVIDENCE.values()))
        self.assertTrue(any("common_complaints" not in record for record in REVIEW_EVIDENCE.values()))


if __name__ == "__main__":
    unittest.main()
