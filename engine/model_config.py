"""Explicit task-based OpenAI model routing.

The application already knows which kind of work it is asking the model to do.
This module maps those known tasks to configurations; it is intentionally not an
LLM-based or learned router.
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ModelTask(str, Enum):
    STRUCTURED_UNDERSTANDING = "structured_understanding"
    CONVERSATIONAL_REASONING = "conversational_reasoning"
    FAST_GROUNDED_GENERATION = "fast_grounded_generation"


@dataclass(frozen=True)
class ModelConfiguration:
    task: ModelTask
    model: str
    reasoning_effort: str


# Model selection starts with the smallest current model. The experiment determines whether
# conversational reasoning earns an escalation to the balanced candidate.
DEFAULT_MODELS = {
    ModelTask.STRUCTURED_UNDERSTANDING: "gpt-5.6-luna",
    ModelTask.CONVERSATIONAL_REASONING: "gpt-5.6-luna",
    ModelTask.FAST_GROUNDED_GENERATION: "gpt-5.6-luna",
}

DEFAULT_REASONING = {
    ModelTask.STRUCTURED_UNDERSTANDING: "none",
    ModelTask.CONVERSATIONAL_REASONING: "low",
    ModelTask.FAST_GROUNDED_GENERATION: "none",
}

MODEL_ENV_VARS = {
    ModelTask.STRUCTURED_UNDERSTANDING: "SHOPPING_MODEL_STRUCTURED",
    ModelTask.CONVERSATIONAL_REASONING: "SHOPPING_MODEL_CONVERSATION",
    ModelTask.FAST_GROUNDED_GENERATION: "SHOPPING_MODEL_FAST",
}


def model_configuration(
    task: ModelTask,
    *,
    model_override: Optional[str] = None,
    reasoning_override: Optional[str] = None,
) -> ModelConfiguration:
    """Resolve one known task without making another model call."""
    model = model_override or os.getenv(MODEL_ENV_VARS[task]) or DEFAULT_MODELS[task]
    effort = reasoning_override or DEFAULT_REASONING[task]
    return ModelConfiguration(task=task, model=model, reasoning_effort=effort)


def responses_request_options(config: ModelConfiguration) -> Dict[str, Any]:
    """Return the Responses API options owned by model configuration.

    GPT-5-family models expose reasoning controls. An environment override may
    intentionally select an older model, so avoid sending an unsupported option
    to non-GPT-5 models.
    """
    options: Dict[str, Any] = {"model": config.model}
    if config.model.startswith("gpt-5"):
        options["reasoning"] = {"effort": config.reasoning_effort}
    return options


CONVERSATIONAL_STRATEGIES = frozenset(
    {
        "clarification",
        "conflict_recovery",
        "no_match_recovery",
        "recovery_rejected",
        "recommendation_pipeline",
        "scoped_guardrail",
    }
)

DETERMINISTIC_STRATEGIES = frozenset({"extraction_recovery"})


def generation_task_for_turn(turn: Dict[str, Any]) -> Optional[ModelTask]:
    """Route a known turn strategy to a model task, or to no model."""
    strategy = turn.get("response_strategy")
    if strategy in DETERMINISTIC_STRATEGIES:
        return None
    if strategy in CONVERSATIONAL_STRATEGIES:
        return ModelTask.CONVERSATIONAL_REASONING
    return ModelTask.FAST_GROUNDED_GENERATION


def public_model_configuration(config: ModelConfiguration) -> Dict[str, str]:
    return {
        "task": config.task.value,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
    }
