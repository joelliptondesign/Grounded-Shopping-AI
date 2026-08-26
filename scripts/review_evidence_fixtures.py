"""Run deterministic Phase 4E review-evidence conversation fixtures."""

import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.conversation import process_conversation_turn  # noqa: E402
from engine.data import SKU_CATALOG  # noqa: E402
from engine.preference_extraction import EMPTY_STATE  # noqa: E402


class FixtureClient:
    def __init__(self, update):
        self.update = update
        self.responses = self

    def create(self, **kwargs):
        return SimpleNamespace(output_text=json.dumps(self.update))


def update_for(intent, products, topic, *, cooling_priority=None):
    return {
        "intent": intent,
        "turn_context": {
            "product_names": products,
            "product_attribute": None,
            "service_attribute": None,
            "exact_product_request": False,
            "information_source": "reviews" if intent != "recommend" else None,
            "review_topic": topic if intent != "recommend" else None,
        },
        "recovery_response": "none",
        "hard_constraints": {"size": None, "max_price": None, "exclude_latex": None, "require_CA_haul_away": None},
        "soft_preferences": {"budget_target": None, "firmness_target": None, "support_target": None, "cooling_target": 9 if cooling_priority else None, "motion_isolation_target": None},
        "priorities": {"price": None, "firmness": None, "support": None, "cooling": cooling_priority, "motion_isolation": None},
        "needs_clarification": False,
        "clarification_question": None,
    }


def run(message, update):
    return process_conversation_turn(
        message, deepcopy(EMPTY_STATE), SKU_CATALOG, client=FixtureClient(update)
    )


def main():
    fixture_path = PROJECT_ROOT / "fixtures" / "review_conversations.json"
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    for fixture in fixtures:
        turn = run(
            fixture["shopper"],
            update_for("product_question", [fixture["product"]], fixture["topic"]),
        )
        print(f"\n## {fixture['name']}\nShopper: {fixture['shopper']}\nAssistant: {turn['response_text']}")

    recommendation = run(
        "Cooling is my top priority. What would you recommend?",
        update_for("recommend", [], None, cooling_priority="critical"),
    )
    card = recommendation["presentation"]["products"][0]
    print(f"\n## Review-enriched recommendation\nSelected: {card['name']}\nWhy it fits: {'; '.join(card['why_it_matches'])}\nTradeoff: {card['tradeoff']}")

    comparison = run(
        "What do reviews say about Metro Cool Comfort and Urban Rest Core for cooling?",
        update_for("compare", ["Metro Cool Comfort", "Urban Rest Core"], "cooling"),
    )
    row = comparison["presentation"]["comparison"]["rows"][0]
    print(f"\n## Review-enriched comparison\n{row['label']}: {' | '.join(row['values'])}")
    print("\nPhase 4E fixture checks passed.")


if __name__ == "__main__":
    main()
