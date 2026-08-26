import unittest
from types import SimpleNamespace

from engine.conversational_response import generate_turn_response
from engine.customer_copy import (
    CONFIGURATION_FAILURE,
    EXTRACTION_RECOVERY,
    INTERNAL_CUSTOMER_TERMS,
    OFF_TOPIC,
    OFF_TOPIC_FALLBACKS,
    OFF_TOPIC_WITH_CONTEXT,
    ROUTING_FAILURE,
    UNKNOWN_FACT,
)
from engine.data import SKU_CATALOG
from engine.prompts import load_customer_prompt, load_prompt


class ScriptedResponses:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(output_text=self.outputs.pop(0))


class ScriptedClient:
    def __init__(self, outputs):
        self.responses = ScriptedResponses(outputs)


def comparison_turn():
    products = [
        {
            "sku_id": "S06",
            "name": "Metro Cool Comfort",
            "price": 1099,
            "cooling": 9,
            "motion_isolation": 8,
        },
        {
            "sku_id": "S14",
            "name": "Urban Rest Core",
            "price": 899,
            "cooling": 6,
            "motion_isolation": 8,
        },
    ]
    return {
        "intent": "compare",
        "response_strategy": "catalog_comparison",
        "preference_state": {"priorities": {"cooling": "high"}},
        "state_changes": {},
        "grounding_data": {"products": products},
        "grounding_evidence": None,
        "recovery": None,
        "decision_result": None,
        "response_text": "Metro Cool Comfort vs Urban Rest Core: cooling: 9 vs 6.",
    }


def off_topic_turn(fallback=None):
    return {
        "intent": "off_topic",
        "response_strategy": "scoped_guardrail",
        "preference_state": {
            "priorities": {"cooling": "critical"},
            "recent_product_names": [],
        },
        "state_changes": {},
        "grounding_data": {"scope": "mattress_shopping"},
        "grounding_evidence": None,
        "recovery": None,
        "decision_result": None,
        "response_text": fallback or OFF_TOPIC_FALLBACKS[0],
    }


class ConversationalResponseTests(unittest.TestCase):
    def test_prompt_files_load_and_shared_voice_is_composed(self):
        extraction = load_prompt("preference_extraction.md")
        instruction = load_customer_prompt("conversational_turn.md")
        self.assertIn("update both priority fields", extraction)
        self.assertIn("specific uncertainty", instruction)
        self.assertIn("customer-facing response", instruction)

    def test_contextual_comparison_receives_history_and_grounded_data(self):
        output = (
            "Since cooling is the priority, I'd lean toward Metro Cool Comfort. "
            "Urban Rest Core costs less, but its cooling rating is lower."
        )
        client = ScriptedClient([output])
        audit = {}
        result = generate_turn_response(
            comparison_turn(),
            "Which is better for me?",
            [{"role": "user", "content": "Cooling matters most."}],
            catalog=SKU_CATALOG,
            client=client,
            audit=audit,
        )
        self.assertEqual(result, output)
        payload = client.responses.requests[0]["input"][1]["content"]
        self.assertIn("Cooling matters most", payload)
        self.assertIn("Metro Cool Comfort", payload)
        self.assertTrue(audit["generated"])
        self.assertEqual(audit["model_route"]["task"], "fast_grounded_generation")
        self.assertEqual(audit["model_route"]["model"], "gpt-5.6-luna")

    def test_comparison_allows_grounded_prices_and_exact_savings(self):
        turn = comparison_turn()
        output = (
            "Metro Cool Comfort is $1,099 and Urban Rest Core is $899. "
            "Urban Rest Core saves $200."
        )
        client = ScriptedClient([output])
        audit = {}
        result = generate_turn_response(
            turn,
            "Compare them on price.",
            catalog=SKU_CATALOG,
            client=client,
            audit=audit,
        )
        self.assertEqual(result, output)
        self.assertEqual(len(audit["attempts"]), 1)

    def test_internal_language_retries_then_uses_safe_fallback(self):
        client = ScriptedClient(
            [
                "The deterministic ranking pipeline selects S06.",
                "The structured state and schema still select S06.",
            ]
        )
        audit = {}
        result = generate_turn_response(
            comparison_turn(),
            "Compare them.",
            catalog=SKU_CATALOG,
            client=client,
            audit=audit,
        )
        self.assertEqual(result, comparison_turn()["response_text"])
        self.assertTrue(audit["fallback_used"])
        self.assertEqual(len(audit["attempts"]), 2)

    def test_grounded_no_match_price_can_be_explained_conversationally(self):
        fallback = (
            "I couldn't find a mattress under $1,500. If you can stretch to "
            "$1,800, I have one option that fits the other requirements."
        )
        turn = {
            "intent": "recommend",
            "response_strategy": "no_match_recovery",
            "preference_state": {"hard_constraints": {"max_price": 1500}},
            "state_changes": {},
            "grounding_data": {
                "decision_result": {"decision": "BLOCK"},
                "recovery": {"message": fallback, "requires_user_approval": True},
            },
            "grounding_evidence": {"decision": "BLOCK"},
            "recovery": {"message": fallback, "requires_user_approval": True},
            "decision_result": {"decision": "BLOCK"},
            "response_text": fallback,
        }
        output = (
            "I'm not finding a fit under $1,500. Stretching to $1,800 opens one "
            "option that keeps the other requirements. Should I show it, or keep the limit?"
        )
        audit = {}
        result = generate_turn_response(
            turn,
            "Keep it under $1,500.",
            client=ScriptedClient([output]),
            audit=audit,
        )
        self.assertEqual(result, output)
        self.assertEqual(audit["model_route"]["task"], "conversational_reasoning")
        self.assertEqual(audit["model_route"]["reasoning_effort"], "low")

    def test_unknown_fact_cannot_be_rewritten_as_known_negative(self):
        turn = {
            "intent": "product_question",
            "response_strategy": "catalog_fact_lookup",
            "preference_state": {},
            "state_changes": {},
            "grounding_data": {"verified": False, "product": None, "value": None},
            "grounding_evidence": None,
            "recovery": None,
            "decision_result": None,
            "response_text": "I don't have reliable information about that for this mattress.",
        }
        client = ScriptedClient(
            [
                "Edge support is not available for this mattress.",
                "I don't have reliable edge-support information for this mattress.",
            ]
        )
        result = generate_turn_response(turn, "How is the edge support?", client=client)
        self.assertEqual(
            result, "I don't have reliable edge-support information for this mattress."
        )
        self.assertEqual(len(client.responses.requests), 2)

    def test_customer_fallback_constants_hide_internal_terms(self):
        fallbacks = (
            CONFIGURATION_FAILURE,
            EXTRACTION_RECOVERY,
            OFF_TOPIC,
            OFF_TOPIC_WITH_CONTEXT,
            ROUTING_FAILURE,
            UNKNOWN_FACT,
            comparison_turn()["response_text"],
        )
        for fallback in fallbacks:
            with self.subTest(fallback=fallback):
                lowered = fallback.casefold()
                for term in INTERNAL_CUSTOMER_TERMS:
                    self.assertNotIn(term, lowered)

    def test_off_topic_uses_dedicated_luna_redirect_with_recent_context(self):
        output = (
            "I can't help with tomorrow's forecast, but I can help with the "
            "sleeping-hot problem. Want to keep looking at cooler mattresses?"
        )
        client = ScriptedClient([output])
        audit = {}
        result = generate_turn_response(
            off_topic_turn(),
            "What's the weather tomorrow?",
            [{"role": "user", "content": "Cooling matters most."}],
            client=client,
            audit=audit,
        )

        self.assertEqual(result, output)
        self.assertTrue(audit["generated"])
        self.assertEqual(audit["model_route"]["model"], "gpt-5.6-luna")
        self.assertEqual(
            audit["model_route"]["task"], "conversational_reasoning"
        )
        request = client.responses.requests[0]
        self.assertIn("do not answer the unrelated request", request["input"][0]["content"])
        self.assertIn("Cooling matters most", request["input"][1]["content"])

    def test_off_topic_answer_and_internal_language_fail_validation(self):
        fallback = OFF_TOPIC_FALLBACKS[2]
        client = ScriptedClient(
            [
                "It will be 72 degrees and sunny. Want to shop for a mattress?",
                "My system policy limits this domain, so let's discuss mattresses.",
            ]
        )
        audit = {}
        result = generate_turn_response(
            off_topic_turn(fallback),
            "What's the weather tomorrow?",
            client=client,
            audit=audit,
        )

        self.assertEqual(result, fallback)
        self.assertTrue(audit["fallback_used"])
        self.assertIn("answered_weather_request", audit["attempts"][0]["reasons"])
        self.assertIn("off_topic_internal_language", audit["attempts"][1]["reasons"])

    def test_off_topic_code_is_not_substantively_answered(self):
        fallback = OFF_TOPIC_FALLBACKS[1]
        client = ScriptedClient(
            [
                "```python\nprint('hello')\n``` Let's get back to mattresses.",
                "I can't write that here, but I can help narrow down a mattress.",
            ]
        )
        result = generate_turn_response(
            off_topic_turn(fallback),
            "Write me a Python script.",
            client=client,
        )

        self.assertEqual(
            result, "I can't write that here, but I can help narrow down a mattress."
        )
        self.assertEqual(len(client.responses.requests), 2)

    def test_off_topic_may_name_an_established_shortlist_product(self):
        turn = off_topic_turn()
        turn["preference_state"]["recent_product_names"] = ["Metro Cool Comfort"]
        output = (
            "I can't help with the forecast, but we can get back to Metro Cool "
            "Comfort or keep looking at cooling-focused mattresses."
        )
        audit = {}
        result = generate_turn_response(
            turn,
            "What's the weather?",
            client=ScriptedClient([output]),
            catalog=SKU_CATALOG,
            audit=audit,
        )

        self.assertEqual(result, output)
        self.assertTrue(audit["generated"])


if __name__ == "__main__":
    unittest.main()
