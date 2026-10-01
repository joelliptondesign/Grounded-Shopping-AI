import unittest
from engine.customer_copy import product_fact_fallback, UNKNOWN_FACT
class MissingEvidence(unittest.TestCase):
 def test_unverified_result_does_not_disclose_product_claim(self):
  self.assertEqual(product_fact_fallback({'verified':False,'product':{'name':'Unsupported claim'}}), UNKNOWN_FACT)
