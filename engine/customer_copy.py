"""Deterministic customer copy used only for guardrails and safe fallbacks."""

import hashlib
from typing import Any, Dict


INTERNAL_CUSTOMER_TERMS = (
    "sku",
    "schema",
    "structured state",
    "constraint violation",
    "grounding",
    "deterministic",
    "pipeline",
    "eligibility",
    "model failure",
    "recommendation engine",
)

EXTRACTION_RECOVERY = (
    "I'm still with you, but I didn't catch what you want to change. "
    "Which part should we focus on—budget, feel, cooling, motion isolation, "
    "or something else?"
)
OFF_TOPIC_FALLBACKS = (
    "I'm better on the mattress side of things. What are you looking for?",
    "That one's outside my lane, but I can help you narrow down a mattress.",
    "I'm here for mattress shopping. Want to keep looking at options?",
    "I can't do much with that one, but I can help you find the right mattress.",
)
OFF_TOPIC_CONTEXT_FALLBACKS = (
    "I'm better on the mattress side of things. Want to keep narrowing down those options?",
    "That one's outside my lane, but we can pick the mattress search back up.",
    "I'm here for mattress shopping. Want to keep refining the options we found?",
    "I can't help much with that one, but I can help with your mattress shortlist.",
)
# Backward-compatible representatives for callers that display or inspect constants.
OFF_TOPIC = OFF_TOPIC_FALLBACKS[0]
OFF_TOPIC_WITH_CONTEXT = OFF_TOPIC_CONTEXT_FALLBACKS[0]
UNKNOWN_FACT = "I don't have reliable information about that for this mattress."
ROUTING_FAILURE = (
    "I'm not sure which part of the mattress search you want to tackle next. "
    "Tell me what you're weighing, and we'll pick it up from there."
)
CONFIGURATION_FAILURE = (
    "I'm unable to start a new shopping conversation right now. Your preferences "
    "haven't changed, so you can try again in a moment."
)


def off_topic_fallback(
    message: str = "", *, has_shopping_context: bool = False
) -> str:
    """Choose stable safe copy without collapsing every off-topic turn to one line."""
    pool = OFF_TOPIC_CONTEXT_FALLBACKS if has_shopping_context else OFF_TOPIC_FALLBACKS
    digest = hashlib.sha256(message.strip().casefold().encode("utf-8")).digest()
    return pool[int.from_bytes(digest[:2], "big") % len(pool)]


def contains_internal_language(text: str) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in INTERNAL_CUSTOMER_TERMS)


def comparison_fallback(result: Dict[str, Any]) -> str:
    products = result["products"]
    if len(products) < 2:
        return "I need two mattresses from this collection to make a useful comparison."
    first, second = products[:2]
    fields = ("price", "firmness", "support", "cooling", "motion_isolation")
    differences = []
    for field in fields:
        first_value = first[field] if field in first else "unknown"
        second_value = second[field] if field in second else "unknown"
        if first_value != second_value:
            differences.append(
                f"{field.replace('_', ' ')}: {first_value} vs {second_value}"
            )
    if not differences:
        return f"{first['name']} and {second['name']} are alike on the details I can verify."
    return f"{first['name']} vs {second['name']}: " + "; ".join(differences) + "."


def product_fact_fallback(result: Dict[str, Any]) -> str:
    if not result["verified"]:
        return UNKNOWN_FACT
    product = result["product"]
    attribute = result["attribute"]
    value = result["value"]
    if attribute == "contains_latex":
        if value:
            return f"{product['name']} is listed as containing latex."
        return f"{product['name']} is listed as not containing latex."
    return f"For {product['name']}, the listed {attribute.replace('_', ' ')} is {value}."


def service_fact_fallback(result: Dict[str, Any]) -> str:
    if not result["verified"]:
        if result.get("service") == "haul_away":
            return "I don't have reliable haul-away information for that mattress."
        return UNKNOWN_FACT
    if result["scope"] == "product":
        product = result["product"]
        if result["available"]:
            return f"California haul-away is available for {product['name']}."
        return f"California haul-away is not available for {product['name']}."
    count = len(result["eligible_products"])
    noun = "mattress" if count == 1 else "mattresses"
    return f"California haul-away is available for {count} {noun} in this collection."


def review_fallback(result: Dict[str, Any]) -> str:
    """Render natural copy using only the supplied review-evidence slice."""
    records = result.get("records", [])
    product_names = result.get("product_names", {})
    topic = result.get("requested_topic", "general")
    if not records:
        return "I don't have enough review information for that mattress."
    if result.get("unknown_topics"):
        name = product_names.get(records[0].get("sku_id"), "this mattress")
        if topic == "unknown":
            return f"I don't have enough review information to answer that for {name}."
        label = topic.replace("_", " ")
        return f"I don't have enough review information about {label} for {name}."

    def decapitalize(text: str) -> str:
        return text[:1].lower() + text[1:] if text else text

    def sentence(record: Dict[str, Any]) -> str:
        name = product_names.get(record.get("sku_id"), "This mattress")
        if topic == "complaints":
            complaints = record.get("common_complaints", [])
            return (f"For {name}, recurring complaints include " + ", ".join(complaints) + ".") if complaints else f"I don't have enough complaint information for {name}."
        if topic == "praise":
            praise = record.get("common_praise", [])
            return (f"For {name}, common praise includes " + ", ".join(praise) + ".") if praise else f"I don't have enough positive review information for {name}."
        if topic not in (None, "general"):
            theme = record.get("themes", {}).get(topic)
            if theme:
                catalog = next((item for item in result.get("catalog_context", []) if item.get("sku_id") == record.get("sku_id")), {})
                if topic in {"firmness", "cooling", "motion_isolation"} and topic in catalog:
                    return f"{name} is listed at {catalog[topic]}/10 for {topic.replace('_', ' ')}, while {decapitalize(theme['summary'])}"
                return f"For {name}, {theme['summary']}"
            return f"I don't have enough review information about {topic.replace('_', ' ')} for {name}."
        themes = list(record.get("themes", {}).values())
        parts = [theme["summary"] for theme in themes[:2]]
        complaints = record.get("common_complaints", [])
        text = f"For {name}, " + " ".join(
            decapitalize(part) if index == 0 else part
            for index, part in enumerate(parts)
        )
        if complaints:
            text += f" A recurring tradeoff is {complaints[0]}."
        return text

    return " ".join(sentence(record) for record in records[:2])
