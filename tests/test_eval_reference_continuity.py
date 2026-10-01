import unittest
from copy import deepcopy
from evals.runner import check_reference_continuity, run_multi_turn, load_documents, make_result


class ReferenceCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.case = next(c for d in load_documents() for c in d["cases"]
                         if c["case_id"] == "v2_compare_and_pick_001")
        self.previous = {"modality": "comparison_table", "products": [{"sku_id": "A"}, {"sku_id": "B"}]}
        self.actual = {"presentation": {"products": [{"sku_id": "B"}]},
                       "shopping_selection": {"selected_product_ids": ["B"], "primary_product_id": "B"}}

    def judge(self, actual, previous=None, expected=None):
        result = make_result(self.case)
        check_reference_continuity(result, expected or {"choose_from_previous_comparison": True},
                                   actual, previous if previous is not None else self.previous, "turn")
        return result.passed

    def test_either_compared_product_can_be_selected(self):
        self.assertTrue(self.judge(self.actual))
        other = deepcopy(self.actual)
        other["presentation"]["products"][0]["sku_id"] = "A"
        other["shopping_selection"] = {"selected_product_ids": ["A"], "primary_product_id": "A"}
        self.assertTrue(self.judge(other))

    def test_outside_empty_and_unrendered_selections_fail(self):
        for chosen, primary, shown in [(["C"], "C", ["C"]), ([], None, []),
                                       (["B"], None, ["B"]), (["B"], "B", ["A"]),
                                       (["B", "B"], "B", ["B", "B"])]:
            with self.subTest(chosen=chosen, primary=primary, shown=shown):
                actual = {"shopping_selection": {"selected_product_ids": chosen, "primary_product_id": primary},
                          "presentation": {"products": [{"sku_id": p} for p in shown]}}
                self.assertFalse(self.judge(actual))

    def test_missing_comparison_fails(self):
        self.assertFalse(self.judge(self.actual, {}))

    def test_wrong_pair_or_order_fails(self):
        prior = {"modality": "recommendation_cards", "products": [{"sku_id": p} for p in ["A", "B", "C"]]}
        for pair in [["B", "A"], ["A", "C"], []]:
            self.assertFalse(self.judge({"presentation": {"products": [{"sku_id": p} for p in pair]}},
                                       prior, {"compare_first_two": True}))
        self.assertTrue(self.judge({"presentation": {"products": prior["products"][:2]}},
                                  prior, {"compare_first_two": True}))

    def test_real_journey_preserves_scope_with_stale_extraction(self):
        self.assertTrue(run_multi_turn(self.case, None).passed)
