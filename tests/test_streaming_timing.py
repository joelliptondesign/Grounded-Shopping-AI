import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response_stream
from engine.data import SKU_CATALOG
from engine.preference_extraction import EMPTY_STATE
from engine.timing import public_timing


def extracted_recommendation():
    return {
        "intent": "recommend",
        "turn_context": {
            "product_names": [],
            "product_attribute": None,
            "service_attribute": None,
            "information_source": None,
            "review_topic": None,
            "exact_product_request": False,
        },
        "hard_constraints": {
            "size": "king",
            "max_price": 2000,
            "exclude_latex": None,
            "require_CA_haul_away": None,
        },
        "soft_preferences": {
            "budget_target": None,
            "firmness_target": None,
            "support_target": None,
            "cooling_target": 9,
            "motion_isolation_target": None,
        },
        "priorities": {
            "price": None,
            "firmness": None,
            "support": None,
            "cooling": "critical",
            "motion_isolation": None,
        },
        "needs_clarification": False,
        "clarification_question": None,
        "recovery_response": "none",
    }


class ExtractionClient:
    def __init__(self, output=None, error=None):
        self.responses = self
        self.output = output
        self.error = error

    def create(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=json.dumps(self.output))


class StreamingResponses:
    def __init__(self, outputs=None, error=None):
        self.outputs = list(outputs or [])
        self.error = error
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        output = self.outputs.pop(0)
        return iter(
            SimpleNamespace(type="response.output_text.delta", delta=piece)
            for piece in output
        )


class StreamingClient:
    def __init__(self, outputs=None, error=None):
        self.responses = StreamingResponses(outputs, error)


class StreamingTimingTests(unittest.TestCase):
    def recommendation_turn(self):
        return process_conversation_turn(
            "I need a king around $2,000. Cooling matters most.",
            deepcopy(EMPTY_STATE),
            SKU_CATALOG,
            client=ExtractionClient(extracted_recommendation()),
        )

    def test_extraction_is_atomic_and_timed_before_decision(self):
        original = deepcopy(EMPTY_STATE)
        with patch("engine.conversation.evaluate_decision") as decision:
            turn = process_conversation_turn(
                "recommend one",
                original,
                SKU_CATALOG,
                client=ExtractionClient(error=ValueError("invalid structured output")),
            )
        decision.assert_not_called()
        self.assertEqual(turn["preference_state"], original)
        timing = turn["timing"]
        self.assertIsNotNone(timing["extraction_started_at"])
        self.assertIsNotNone(timing["extraction_completed_at"])
        self.assertIsNotNone(timing["decision_ready_at"])
        self.assertIsNotNone(timing["presentation_ready_at"])

    def test_streaming_does_not_change_decision_rank_or_modality(self):
        turn = self.recommendation_turn()
        decision_before = deepcopy(turn["decision_result"])
        modality_before = turn["modality"]
        fallback = turn["response_text"]
        client = StreamingClient([[fallback]])
        delivered = "".join(
            generate_turn_response_stream(turn, "recommend one", catalog=SKU_CATALOG, client=client)
        )
        self.assertEqual(delivered, fallback)
        self.assertEqual(turn["decision_result"], decision_before)
        self.assertEqual(turn["modality"], modality_before)
        self.assertEqual(
            [item["sku_id"] for item in turn["decision_result"]["ranked_candidates"]],
            [item["sku_id"] for item in decision_before["ranked_candidates"]],
        )

    def test_invalid_streamed_claim_is_never_yielded(self):
        turn = self.recommendation_turn()
        bad = "I recommend an imaginary mattress for $99."
        safe = turn["response_text"]
        audit = {}
        delivered = "".join(
            generate_turn_response_stream(
                turn,
                "recommend one",
                catalog=SKU_CATALOG,
                client=StreamingClient([[bad], [safe]]),
                audit=audit,
            )
        )
        self.assertEqual(delivered, safe)
        self.assertNotIn("imaginary", delivered)
        self.assertEqual(len(audit["attempts"]), 2)
        self.assertEqual(audit["delivery"], "validation_buffered_stream")

    def test_generation_failure_yields_deterministic_fallback(self):
        turn = self.recommendation_turn()
        delivered = "".join(
            generate_turn_response_stream(
                turn,
                "recommend one",
                catalog=SKU_CATALOG,
                client=StreamingClient(error=RuntimeError("generation failed")),
            )
        )
        timing = public_timing(turn["timing"])
        self.assertEqual(delivered, turn["response_text"])
        self.assertEqual(timing["response_path"], "deterministic_fallback")
        self.assertEqual(timing["generation_status"], "failed")
        self.assertIsNotNone(timing["generation_completed_at"])
        self.assertIsNotNone(timing["turn_completed_at"])

    def test_stream_records_first_token_completion_and_total_latency(self):
        turn = self.recommendation_turn()
        fallback = turn["response_text"]
        list(
            generate_turn_response_stream(
                turn,
                "recommend one",
                catalog=SKU_CATALOG,
                client=StreamingClient([[fallback[:10], fallback[10:]]]),
            )
        )
        timing = public_timing(turn["timing"])
        self.assertEqual(timing["response_path"], "streamed")
        for field in (
            "generation_started_at",
            "first_token_at",
            "generation_completed_at",
            "response_visible_at",
            "turn_completed_at",
        ):
            self.assertIsNotNone(timing[field])
        for metric in (
            "extraction_latency",
            "decision_ready_latency",
            "presentation_ready_latency",
            "generation_ttft",
            "generation_latency",
            "total_turn_latency",
        ):
            self.assertIsNotNone(timing["metrics_ms"][metric])
            self.assertGreaterEqual(timing["metrics_ms"][metric], 0)


if __name__ == "__main__":
    unittest.main()
