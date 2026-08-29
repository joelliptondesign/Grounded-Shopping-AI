"""Isolate the latency of each model call on the Live critical path.

Runs the real selection and generation prompts at different reasoning efforts so
routing changes can be judged on measurements rather than intuition.
"""

import json, os, statistics, sys, time
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from openai import OpenAI

from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision
from engine.preference_extraction import new_preference_state, to_decision_preferences
from engine.shopping_selection import (
    BASE_SELECTION_INSTRUCTION, SHOPPING_SELECTION_SCHEMA,
    validate_shopping_selection,
)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("SHOPPING_MODEL_CONVERSATION", "gpt-5.6-luna")


def shopper(size="queen", budget=1400, priorities=("cooling", "motion_isolation")):
    state = new_preference_state()
    state["hard_constraints"]["size"] = size
    state["soft_preferences"]["budget_target"] = budget
    for field in priorities:
        state["priorities"][field] = "critical"
    state["recommendation_readiness"] = "strong"
    return state


def selection_payload(state, candidates, decision):
    scores = {i.get("sku_id"): i for i in decision.get("metadata", {}).get("candidate_scores", [])}
    return {
        "current_shopper_message": "I need a queen mattress around $1400. Cooling and motion isolation matter most.",
        "shopper_state": deepcopy(state),
        "recent_conversation": [],
        "recently_shown_or_referenced_products": [],
        "eligible_candidates": [
            {**deepcopy(c),
             "deterministic_score_signal": scores.get(c.get("sku_id"), {}).get("score"),
             "deterministic_rank_signal": scores.get(c.get("sku_id"), {}).get("current_rank"),
             "represented_tradeoffs": deepcopy(
                 decision.get("metadata", {}).get("preference_tradeoffs", {}).get(c.get("sku_id"), []))}
            for c in candidates],
        "represented_review_evidence": {},
    }


def run_selection(effort, payload, candidates, prefs, runs):
    latencies, picks, valid = [], [], 0
    options = {"model": MODEL}
    if effort is not None:
        options["reasoning"] = {"effort": effort}
    for _ in range(runs):
        started = time.perf_counter()
        try:
            response = client.responses.create(
                **options,
                input=[{"role": "system", "content": BASE_SELECTION_INSTRUCTION},
                       {"role": "user", "content": json.dumps(payload)}],
                text={"format": {"type": "json_schema", "name": "shopping_product_selection",
                                 "schema": SHOPPING_SELECTION_SCHEMA, "strict": True}},
            )
        except Exception as error:
            print(f"    error: {type(error).__name__}: {error}")
            continue
        latencies.append((time.perf_counter() - started) * 1000)
        selection = json.loads(response.output_text)
        result = validate_shopping_selection(selection, candidates, prefs)
        valid += bool(result["valid"])
        picks.append((selection["selection_mode"],
                      tuple(i["product_id"] for i in selection["selections"])))
        usage = getattr(response, "usage", None)
        if usage is not None and not hasattr(run_selection, "_logged"):
            run_selection._logged = True
            print(f"    tokens in={usage.input_tokens} out={usage.output_tokens}")
    return latencies, picks, valid


def summarise(label, latencies, picks, valid, runs):
    if not latencies:
        print(f"  {label:<26} no successful runs")
        return
    ordered = sorted(latencies)
    p50 = ordered[len(ordered) // 2]
    p90 = ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]
    print(f"  {label:<26} p50 {p50:7.0f} ms  p90 {p90:7.0f} ms  valid {valid}/{runs}")
    for pick in sorted(set(picks)):
        print(f"      {pick[0]:<22} {' '.join(pick[1])}  x{picks.count(pick)}")


if __name__ == "__main__":
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    state = shopper()
    prefs = to_decision_preferences(state)
    decision = evaluate_decision(prefs, SKU_CATALOG)
    candidates = decision["ranked_candidates"]
    payload = selection_payload(state, candidates, decision)
    print(f"shopping selection — {len(candidates)} candidates, model {MODEL}, {runs} runs each\n")
    for effort in ("low", "none", "minimal"):
        latencies, picks, valid = run_selection(effort, payload, candidates, prefs, runs)
        summarise(f"reasoning={effort}", latencies, picks, valid, runs)
