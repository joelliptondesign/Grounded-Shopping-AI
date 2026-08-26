import inspect
import unittest

from streamlit.testing.v1 import AppTest

import streamlit_app
from engine.customer_copy import (
    CONFIGURATION_FAILURE,
    INTERNAL_CUSTOMER_TERMS,
    OFF_TOPIC,
    OFF_TOPIC_WITH_CONTEXT,
)


class StreamlitProductBoundaryTests(unittest.TestCase):
    def run_app(self):
        return AppTest.from_file("streamlit_app.py", default_timeout=10).run()

    def test_shopping_agent_is_the_default_without_legacy_controls(self):
        app = self.run_app()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual([title.value for title in app.title], ["Mattress Shopping Agent"])
        self.assertEqual(app.radio[0].value, "Shopping Agent")
        self.assertEqual(len(app.selectbox), 0)
        self.assertEqual(len(app.text_area), 0)
        self.assertEqual([item.label for item in app.checkbox], ["Developer details"])
        self.assertEqual(
            app.chat_input[0].placeholder,
            "What are you looking for in a mattress?",
        )

    def test_legacy_experiment_and_controls_are_secondary(self):
        app = self.run_app()
        app.radio[0].set_value("Advanced / Experiments").run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual([title.value for title in app.title], ["Original A/B Experiment"])
        self.assertEqual([item.label for item in app.selectbox], ["Scenario"])
        self.assertEqual([item.label for item in app.text_area], ["Query"])
        self.assertEqual(
            [item.label for item in app.button],
            ["Run baseline", "Run decision layer"],
        )

    def test_developer_details_remain_available_only_on_disclosure(self):
        app = self.run_app()
        self.assertEqual(len(app.expander), 0)

        app.checkbox[0].check().run()

        self.assertIn(
            "Current structured shopping state",
            [item.label for item in app.expander],
        )

    def test_structured_cards_and_comparison_tables_render(self):
        app = self.run_app()
        app.session_state["messages"] = [
            {
                "role": "assistant",
                "content": "I'd start here.",
                "presentation": {
                    "modality": "recommendation_cards",
                    "message": "I'd start here.",
                    "products": [
                        {
                            "name": "Test Mattress",
                            "price": 999,
                            "why_it_matches": ["Cooling: 9/10"],
                            "tradeoff": None,
                            "service_indicator": None,
                        }
                    ],
                    "actions": [],
                    "suggested_replies": [],
                },
            }
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        self.assertIn("#### Test Mattress", [item.value for item in app.markdown])

        app.session_state["messages"] = [
            {
                "role": "assistant",
                "content": "Here's the comparison.",
                "presentation": {
                    "modality": "comparison_table",
                    "message": "Here's the comparison.",
                    "products": [],
                    "comparison": {
                        "products": ["One", "Two"],
                        "rows": [{"label": "Price", "values": ["$999", "$1,199"]}],
                    },
                    "actions": [],
                    "suggested_replies": [],
                },
            }
        ]
        app.run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 1)

    def test_primary_chat_uses_current_conversation_entry_point_only(self):
        source = inspect.getsource(streamlit_app.render_shopping_agent)

        self.assertIn("process_conversation_turn", source)
        self.assertNotIn("query_in_scope", source)
        self.assertNotIn("get_decision_explanation", source)
        self.assertNotIn("evaluate_decision", source)

    def test_customer_fallbacks_do_not_expose_internal_language(self):
        for message in (OFF_TOPIC, OFF_TOPIC_WITH_CONTEXT, CONFIGURATION_FAILURE):
            with self.subTest(message=message):
                lowered = message.casefold()
                for term in INTERNAL_CUSTOMER_TERMS:
                    self.assertNotIn(term, lowered)
                self.assertNotIn("please adjust your query", lowered)


if __name__ == "__main__":
    unittest.main()
