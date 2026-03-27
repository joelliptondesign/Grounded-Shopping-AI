# Decision Layer Shopping Demo

This repository is a customer-facing AI shopping demo for mattress recommendations. The visible experience is conversational, but the recommendation itself is determined by code, not by the language model.

A deterministic decision layer sits underneath the UI. It applies explicit constraints, filters invalid options, ranks the remaining SKUs, and produces a structured outcome before any customer-facing explanation is written.

The LLM explains the selected outcome. It does not decide which product is valid. This separation is intended to avoid plausible but incorrect answers about recommendation eligibility, delivery, or service coverage.

## Why This Exists

High-consideration shopping often combines product preferences with operational constraints. A shopper may care about cooling, firmness, budget, and delivery requirements at the same time.

Those combinations are where baseline LLM behavior can become misleading. A model can sound confident while overlooking a hard constraint or implying a service commitment that the catalog does not support. This repo demonstrates a narrower pattern: make validity decisions in code first, then generate customer-facing language on top of that result.

## What the System Does

- Collects user preferences from curated demo scenarios and chat inputs
- Applies hard constraints such as budget and latex exclusion
- Enforces service eligibility rules such as California haul-away availability
- Ranks valid candidates deterministically with stable ordering
- Selects the top valid SKU or returns an explicit blocked outcome
- Generates a customer-facing explanation for the resulting outcome

## Architecture / Repo Signal

The core engineering point is that recommendation enforcement is explicit in code. Validity is determined before language generation, and the UI presents that result in customer-safe language.

The backend keeps structured decision and action output available for inspection. In the Streamlit demo, those internal details are hidden by default and can be viewed only through the optional developer toggle.

## Example: Structured Decision Output

Input:

```json
{
  "max_price": 1500,
  "firmness_preference": 6,
  "support_preference": 7,
  "cooling_preference": 8,
  "motion_isolation_preference": 8,
  "query_text": "Do these mattresses on Amazon include room-of-choice delivery, in-home setup, or haul-away service?",
  "require_CA_haul_away": true
}
```

Output:

```json
{
  "decision": "ALLOW",
  "reason": "valid_recommendation",
  "violations": [],
  "selected_sku": {
    "sku_id": "S08",
    "name": "Everrest Breeze 8",
    "price": 1349
  },
  "action": {
    "type": "recommendation",
    "status": "ready",
    "sku_id": "S08"
  },
  "metadata": {
    "haul_away_requested": true,
    "zip_code": null,
    "candidate_count": 9
  }
}
```

## Programmatic Usage

```python
from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision

preferences = {
    "max_price": 1500,
    "firmness_preference": 6,
    "support_preference": 7,
    "cooling_preference": 8,
    "motion_isolation_preference": 8,
    "query_text": "Do these mattresses on Amazon include room-of-choice delivery, in-home setup, or haul-away service?",
    "require_CA_haul_away": True,
}

result = evaluate_decision(preferences, SKU_CATALOG)
print(result)
```

## Curated Demo Scenarios

- `High Cooling Performance Under Budget`: shows a normal valid recommendation flow with strong cooling and motion-isolation preferences under budget.
- `Haul-Away Required`: shows service-rule enforcement when California haul-away availability is required.
- `Impossible Cooling Spec`: shows a constrained shopping case where the top cooling preference must still respect the available catalog and budget.

## Running the Demo

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Run the CLI demo:

```bash
python3 app.py
```

Run the Streamlit UI:

```bash
streamlit run streamlit_app.py
```

Create a `.env` file in the repo root if you want live explanation calls:

```bash
OPENAI_API_KEY=your_key_here
```

If `OPENAI_API_KEY` is missing, the explanation layer falls back to deterministic local output. The Streamlit UI still runs.

## Repo Structure

- `streamlit_app.py`: customer-facing demo UI with side-by-side baseline and decision-layer views.
- `engine/decision.py`: deterministic constraint enforcement, ranking, selection, and structured decision output.
- `engine/explanation_llm.py`: customer-facing explanation generation with deterministic fallback behavior.
- `engine/baseline_llm.py`: baseline LLM path used for comparison against the decision layer.
- `engine/data.py`: curated in-repo mattress catalog used by the demo.

## Notes / Scope

This is a narrow demo repository, not a production shopping system. It is intentionally scenario-driven and focused on showing deterministic decision support beneath a conversational surface.
