import json
import unittest
from pathlib import Path

from engine.customer_copy import INTERNAL_CUSTOMER_TERMS


class ConversationFixtureTests(unittest.TestCase):
    def test_required_qualitative_fixtures_are_present_and_customer_safe(self):
        path = Path(__file__).resolve().parent.parent / "fixtures" / "conversational_voice.json"
        fixtures = json.loads(path.read_text(encoding="utf-8"))
        names = {fixture["name"] for fixture in fixtures}
        self.assertEqual(
            names,
            {
                "Fuzzy preference",
                "Ambiguous budget",
                "Priority change",
                "No exact match",
                "Constraint conflict",
                "Comparison",
                "Unknown product information",
            },
        )
        for fixture in fixtures:
            assistant_turns = [
                turn["content"] for turn in fixture["turns"] if turn["role"] == "assistant"
            ]
            self.assertTrue(assistant_turns)
            for response in assistant_turns:
                lowered = response.casefold()
                for term in INTERNAL_CUSTOMER_TERMS:
                    self.assertNotIn(term, lowered)


if __name__ == "__main__":
    unittest.main()
