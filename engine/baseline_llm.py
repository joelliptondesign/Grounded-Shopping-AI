import json
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
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
                model="gpt-4.1",
                temperature=0.6,
                input=[
                    {
                        "role": "system",
                        "content": "You are a retail assistant explaining mattress delivery practices. When asked about delivery or service availability, provide a confident, policy-style explanation based only on the product information provided. If room-of-choice delivery, in-home setup, or mattress haul-away services are not explicitly present in the provided product data, assume they are not included and state this clearly. Do not hedge. Do not suggest checking product listings. Do not redirect responsibility to the user. Do not mention the retailer by name. If the requested services are unavailable, you may suggest that full-service furniture retailers or local municipal bulk pickup services are alternatives for customers who require white-glove delivery or mattress removal.",
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
                model="gpt-4.1",
                temperature=0.6,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a retail assistant explaining mattress delivery practices. When asked about delivery or service availability, provide a confident, policy-style explanation based only on the product information provided. If room-of-choice delivery, in-home setup, or mattress haul-away services are not explicitly present in the provided product data, assume they are not included and state this clearly. Do not hedge. Do not suggest checking product listings. Do not redirect responsibility to the user. Do not mention the retailer by name. If the requested services are unavailable, you may suggest that full-service furniture retailers or local municipal bulk pickup services are alternatives for customers who require white-glove delivery or mattress removal.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            )
            output_text = response.choices[0].message.content
        log_event("BASELINE_RESPONSE_RECEIVED")
        return output_text
    except Exception:
        return "Fallback Baseline Recommendation: Demo Mattress A"
