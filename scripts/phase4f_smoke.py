"""Deterministic Phase 4F smoke scenarios without network model calls."""

import json
from copy import deepcopy
from types import SimpleNamespace

from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response_stream
from engine.data import SKU_CATALOG
from engine.preference_extraction import EMPTY_STATE
from engine.timing import mark_timing, public_timing


def update(intent, **context):
    hard = context.pop("hard", {})
    soft = context.pop("soft", {})
    priorities = context.pop("priorities", {})
    return {
        "intent": intent,
        "turn_context": {
            "product_names": [],
            "product_attribute": None,
            "service_attribute": None,
            "information_source": None,
            "review_topic": None,
            "exact_product_request": False,
            **context,
        },
        "hard_constraints": {
            "size": None,
            "max_price": None,
            "exclude_latex": None,
            "require_CA_haul_away": None,
            **hard,
        },
        "soft_preferences": {
            "budget_target": None,
            "firmness_target": None,
            "support_target": None,
            "cooling_target": None,
            "motion_isolation_target": None,
            **soft,
        },
        "priorities": {
            "price": None,
            "firmness": None,
            "support": None,
            "cooling": None,
            "motion_isolation": None,
            **priorities,
        },
        "needs_clarification": False,
        "clarification_question": None,
        "recovery_response": "none",
    }


class ExtractionClient:
    def __init__(self, payload):
        self.responses = self
        self.payload = payload

    def create(self, **kwargs):
        return SimpleNamespace(output_text=json.dumps(self.payload))


class GenerationClient:
    def __init__(self, text=None, fail=False):
        self.responses = self
        self.text = text
        self.fail = fail

    def create(self, **kwargs):
        if self.fail:
            raise RuntimeError("simulated generation failure")
        midpoint = max(1, len(self.text) // 2)
        return iter(
            [
                SimpleNamespace(
                    type="response.output_text.delta", delta=self.text[:midpoint]
                ),
                SimpleNamespace(
                    type="response.output_text.delta", delta=self.text[midpoint:]
                ),
            ]
        )


def run_turn(name, message, extraction, state, previous=None, fail=False):
    turn = process_conversation_turn(
        message,
        state,
        SKU_CATALOG,
        client=ExtractionClient(extraction),
        previous_decision_result=previous,
    )
    if turn["modality"] != "conversation":
        mark_timing(turn["timing"], "presentation_visible_at")
    response = "".join(
        generate_turn_response_stream(
            turn,
            message,
            catalog=SKU_CATALOG,
            client=GenerationClient(turn["response_text"], fail=fail),
        )
    )
    if not response:
        raise AssertionError(f"{name} produced an empty response")
    result = {
        "scenario": name,
        "intent": turn["intent"],
        "modality": turn["modality"],
        "decision": (turn.get("decision_result") or {}).get("decision"),
        "response_path": turn["timing"]["response_path"],
        "timing_ms": public_timing(turn["timing"])["metrics_ms"],
    }
    print(json.dumps(result, sort_keys=True))
    return turn


def main():
    state = deepcopy(EMPTY_STATE)
    recommendation = run_turn(
        "recommendation",
        "I need a king around $2,000. Cooling matters most.",
        update(
            "recommend",
            hard={"size": "king"},
            soft={"budget_target": 2000, "cooling_target": 9},
            priorities={"cooling": "critical"},
        ),
        state,
    )
    state = recommendation["preference_state"]
    ranked = recommendation["decision_result"]["ranked_candidates"]
    names = [ranked[0]["name"], ranked[1]["name"]]
    comparison = run_turn(
        "comparison",
        "Compare the first two.",
        update("compare", product_names=names),
        state,
        recommendation["decision_result"],
    )
    run_turn(
        "review_question",
        "What do owners say about cooling on the first one?",
        update(
            "product_question",
            product_names=[names[0]],
            information_source="reviews",
            review_topic="cooling",
        ),
        comparison["preference_state"],
        recommendation["decision_result"],
    )
    recovery = run_turn(
        "recovery",
        "I need a king mattress under $100 maximum.",
        update("recommend", hard={"size": "king", "max_price": 100}),
        state,
        recommendation["decision_result"],
    )
    if recovery["decision_result"]["decision"] != "BLOCK":
        raise AssertionError("Recovery smoke did not reach a blocked decision")
    run_turn(
        "generation_failure",
        "I need a king around $2,000. Cooling matters most.",
        update(
            "recommend",
            hard={"size": "king"},
            soft={"budget_target": 2000, "cooling_target": 9},
            priorities={"cooling": "critical"},
        ),
        deepcopy(EMPTY_STATE),
        fail=True,
    )


if __name__ == "__main__":
    main()
