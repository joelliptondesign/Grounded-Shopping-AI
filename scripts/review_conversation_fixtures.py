"""Print Phase 4C.5 voice fixtures and enforce objective copy guardrails."""

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.customer_copy import INTERNAL_CUSTOMER_TERMS  # noqa: E402


FIXTURE_PATH = PROJECT_ROOT / "fixtures" / "conversational_voice.json"


def main() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    required = {
        "Fuzzy preference",
        "Ambiguous budget",
        "Priority change",
        "No exact match",
        "Constraint conflict",
        "Comparison",
        "Unknown product information",
    }
    names = {fixture["name"] for fixture in fixtures}
    missing = required - names
    if missing:
        raise SystemExit(f"Missing fixtures: {', '.join(sorted(missing))}")

    for fixture in fixtures:
        print(f"\n## {fixture['name']}")
        for turn in fixture["turns"]:
            content = turn["content"]
            if turn["role"] == "assistant":
                lowered = content.casefold()
                leaked = [term for term in INTERNAL_CUSTOMER_TERMS if term in lowered]
                if leaked:
                    raise SystemExit(
                        f"{fixture['name']} exposes internal terms: {', '.join(leaked)}"
                    )
            print(f"{turn['role'].title()}: {content}")
        print("Review for: " + "; ".join(fixture["review_for"]))

    print(f"\nReviewed {len(fixtures)} conversational fixtures; objective copy checks passed.")


if __name__ == "__main__":
    main()
