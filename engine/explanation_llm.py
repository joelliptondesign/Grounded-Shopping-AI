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


def build_customer_explanation(selected_sku, structured_facts):
    name = selected_sku.get("name", "selected mattress")
    price = selected_sku.get("price")
    firmness = selected_sku.get("firmness")
    support = selected_sku.get("support")
    cooling = selected_sku.get("cooling")
    motion_isolation = selected_sku.get("motion_isolation")
    prefs = structured_facts.get("user_preferences", {})
    budget = prefs.get("max_price")
    if budget is None:
        budget = "N/A"

    lines = [
        f"### {name}",
        "",
        "Why this is a strong match for you:",
        "",
        f"• Price: ${price} — comfortably within your ${budget} budget",
        f"• Firmness: {firmness}/10 — aligned with your preference",
        f"• Support: {support}/10",
        f"• Cooling: {cooling}/10",
        f"• Motion Isolation: {motion_isolation}/10",
        "",
        "Delivery & Service",
        "",
    ]

    if prefs.get("require_CA_haul_away") is True:
        lines.append(
            "Because you're purchasing in California, this mattress qualifies for Amazon's state-compliant haul-away service, which addresses your delivery requirement."
        )
    else:
        lines.append(
            "This mattress supports haul-away service on Amazon, meeting your stated delivery needs."
        )

    lines.extend(
        [
            "",
            "Summary",
            "",
            f"The {name} delivers the comfort and performance you're prioritizing while also satisfying your delivery requirement.",
        ]
    )
    return "\n".join(lines)


def build_decision_explanation(decision_result, structured_facts):
    decision = decision_result.get("decision")
    selected_sku = decision_result.get("selected_sku")

    if decision == "BLOCK":
        return (
            "I couldn't find a mattress that matches all of those requirements. "
            "Try adjusting the budget or relaxing a service requirement, then run it again."
        )

    if selected_sku is None:
        return "No recommendation is available."

    return build_customer_explanation(selected_sku, structured_facts)


def get_explanation(selected_sku, structured_facts, decision_result=None):
    if decision_result is not None and decision_result.get("decision") == "BLOCK":
        return build_decision_explanation(decision_result, structured_facts)

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        if decision_result is not None:
            return build_decision_explanation(decision_result, structured_facts)
        return build_customer_explanation(selected_sku, structured_facts)

    client = OpenAI(api_key=api_key)
    prompt = {
        "task": "Explain the explicit decision outcome.",
        "decision_result": decision_result,
        "selected_sku": selected_sku,
        "structured_facts": structured_facts,
    }

    log_event("EXPLANATION_PROMPT_SENT")
    try:
        system_instruction = (
            "You are formatting a customer-facing explanation for an explicit mattress decision outcome. "
            "Use only the provided structured facts. Do not infer additional services or constraints. "
            "Do not mention internal scoring or selection logic. If the decision is ALLOW, present the response "
            "with: (1) a clear product header including name and price, (2) bullet points aligning features to "
            "user preferences, (3) a ‘Delivery & Service’ section that reflects structured service facts only, "
            "and (4) a concise summary. If the decision is BLOCK, provide a concise explanation that no "
            "suitable match was found without mentioning internal labels, codes, or identifiers."
        )
        if hasattr(client, "responses"):
            response = client.responses.create(
                model="gpt-4.1",
                temperature=0.4,
                input=[
                    {
                        "role": "system",
                        "content": system_instruction,
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
                temperature=0.4,
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction,
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
            )
            output_text = response.choices[0].message.content
        log_event("EXPLANATION_RESPONSE_RECEIVED")
        return output_text
    except Exception:
        if decision_result is not None:
            return build_decision_explanation(decision_result, structured_facts)
        return build_customer_explanation(selected_sku, structured_facts)
