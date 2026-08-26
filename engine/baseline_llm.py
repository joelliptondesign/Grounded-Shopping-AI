import json
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

from engine.prompts import load_prompt
from engine.model_config import (
    ModelTask,
    model_configuration,
    responses_request_options,
)
import os


LOG_FILE = "logs/debug.log"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(event_name: str) -> None:
    line = f"{utc_timestamp()} | {event_name}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_baseline_recommendation(user_preferences, sku_catalog):
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return "Fallback Baseline Recommendation: Demo Mattress A"

    client = OpenAI(api_key=api_key)
    config = model_configuration(ModelTask.CONVERSATIONAL_REASONING)
    sanitized_catalog = []
    for sku in sku_catalog:
        cleaned_sku = dict(sku)
        cleaned_sku.pop("haul_away_CA_available", None)
        sanitized_catalog.append(cleaned_sku)
    sanitized_preferences = dict(user_preferences)
    sanitized_preferences.pop("require_CA_haul_away", None)
    prompt = {
        "task": "Recommend the best mattress for the user.",
        "user_preferences": sanitized_preferences,
        "sku_catalog": sanitized_catalog,
    }

    log_event("BASELINE_PROMPT_SENT")
    try:
        if hasattr(client, "responses"):
            response = client.responses.create(
                **responses_request_options(config),
                input=[
                    {
                        "role": "system",
                        "content": load_prompt("baseline_delivery.md"),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt),
                    },
                ],
            )
            output_text = response.output_text
        else:
            response = client.chat.completions.create(
                model=config.model,
                messages=[
                    {
                        "role": "system",
                        "content": load_prompt("baseline_delivery.md"),
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            )
            output_text = response.choices[0].message.content
        log_event("BASELINE_RESPONSE_RECEIVED")
        return output_text
    except Exception:
        return "Fallback Baseline Recommendation: Demo Mattress A"
