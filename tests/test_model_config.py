import os
import unittest
from unittest.mock import patch

from engine.model_config import (
    ModelTask,
    generation_task_for_turn,
    model_configuration,
    responses_request_options,
)


class ModelConfigurationTests(unittest.TestCase):
    def test_defaults_start_with_smallest_current_candidate(self):
        for task in ModelTask:
            with self.subTest(task=task):
                self.assertEqual(model_configuration(task).model, "gpt-5.6-luna")

    def test_environment_overrides_are_task_specific(self):
        with patch.dict(
            os.environ,
            {
                "SHOPPING_MODEL_STRUCTURED": "structured-test",
                "SHOPPING_MODEL_CONVERSATION": "conversation-test",
                "SHOPPING_MODEL_FAST": "fast-test",
            },
        ):
            self.assertEqual(
                model_configuration(ModelTask.STRUCTURED_UNDERSTANDING).model,
                "structured-test",
            )
            self.assertEqual(
                model_configuration(ModelTask.CONVERSATIONAL_REASONING).model,
                "conversation-test",
            )
            self.assertEqual(
                model_configuration(ModelTask.FAST_GROUNDED_GENERATION).model,
                "fast-test",
            )

    def test_known_context_routes_without_a_model_router(self):
        self.assertEqual(
            generation_task_for_turn({"response_strategy": "clarification"}),
            ModelTask.CONVERSATIONAL_REASONING,
        )
        self.assertEqual(
            generation_task_for_turn({"response_strategy": "catalog_comparison"}),
            ModelTask.FAST_GROUNDED_GENERATION,
        )
        self.assertEqual(
            generation_task_for_turn({"response_strategy": "scoped_guardrail"}),
            ModelTask.CONVERSATIONAL_REASONING,
        )

    def test_reasoning_controls_are_attached_to_gpt5_responses(self):
        config = model_configuration(ModelTask.CONVERSATIONAL_REASONING)
        self.assertEqual(
            responses_request_options(config)["reasoning"], {"effort": "low"}
        )


if __name__ == "__main__":
    unittest.main()
