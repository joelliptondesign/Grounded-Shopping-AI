import json
from datetime import datetime, timezone

from engine.baseline_llm import get_baseline_recommendation
from engine.data import SKU_CATALOG
from engine.decision import select_top_sku
from engine.explanation_llm import get_explanation


LOG_FILE = "logs/debug.log"
GOVERNANCE_KEYWORDS = (
    "mattress",
    "sleep",
    "firmness",
    "cooling",
    "motion",
    "budget",
    "trial",
    "allergy",
    "latex",
)

GOVERNANCE_MESSAGE = (
    "This demonstration is scoped to structured mattress recommendation scenarios. "
    "Please adjust your query accordingly."
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(message: str) -> None:
    line = f"{utc_timestamp()} | {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def query_in_scope(query_text: str) -> bool:
    lowered = str(query_text).lower()
    return any(keyword in lowered for keyword in GOVERNANCE_KEYWORDS)


def main() -> None:
    user_preferences = {
        "max_price": 1400,
        "firmness_preference": 6,
        "support_preference": 8,
        "cooling_preference": 7,
        "motion_isolation_preference": 8,
        "query_text": "",
    }

    if not query_in_scope(user_preferences.get("query_text", "")):
        print(GOVERNANCE_MESSAGE)
        return

    print("=== BASELINE SYSTEM ===")
    baseline_output = get_baseline_recommendation(user_preferences, SKU_CATALOG)
    print(baseline_output)

    print("=== DECISION LAYER SYSTEM ===")
    selected_sku = select_top_sku(user_preferences, SKU_CATALOG)
    print(json.dumps(selected_sku, indent=2))

    explanation_facts = {
        "selected_sku_id": selected_sku["sku_id"],
        "selected_name": selected_sku["name"],
        "selected_price": selected_sku["price"],
        "user_preferences": user_preferences,
        "deterministic_selection": True,
    }
    explanation_output = get_explanation(selected_sku, explanation_facts)
    print(explanation_output)

    log_event("APP_RUN_COMPLETED")


if __name__ == "__main__":
    main()
