"""Explicit, grounded response strategies for non-recommendation turns."""

from typing import Any, Dict, Iterable, List, Optional

from engine.grounding import AUTHORITATIVE_SOURCES
from engine.customer_copy import (
    OFF_TOPIC,
    UNKNOWN_FACT,
    comparison_fallback,
    product_fact_fallback,
    service_fact_fallback,
    review_fallback,
)
from engine.review_data import review_slice


OFF_TOPIC_RESPONSE = OFF_TOPIC
UNVERIFIED_RESPONSE = UNKNOWN_FACT

PRODUCT_FACT_FIELDS = (
    "sku_id",
    "name",
    "price",
    "available_sizes",
    "firmness",
    "support",
    "cooling",
    "motion_isolation",
    "materials",
    "contains_latex",
    "trial_days",
    "warranty_years",
    "haul_away_CA_available",
)


def strategy_for_intent(intent: str) -> str:
    """Return the inspectable response strategy for a primary intent."""
    strategies = {
        "recommend": "recommendation_pipeline",
        "compare": "catalog_comparison",
        "product_question": "catalog_fact_lookup",
        "service_question": "service_fact_lookup",
        "off_topic": "scoped_guardrail",
    }
    return strategies[intent]


def build_review_fact(
    product_names: Iterable[str],
    topic: Optional[str],
    catalog: Iterable[Dict[str, Any]],
    *,
    fallback_product: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve products through the catalog, then retrieve a narrow review slice."""
    products = find_products(product_names, catalog)
    if not products and fallback_product:
        products = [fallback_product]
    evidence = review_slice([product["sku_id"] for product in products], topic)
    evidence.update(
        {
            "intent": "product_question",
            "requested_products": list(product_names),
            "product_names": {product["sku_id"]: product["name"] for product in products},
            "catalog_context": [
                {
                    key: product[key]
                    for key in ("sku_id", "name", topic)
                    if key and key in product
                }
                for product in products
            ],
        }
    )
    return evidence


def add_comparison_reviews(
    comparison: Dict[str, Any], topic: Optional[str]
) -> Dict[str, Any]:
    evidence = review_slice(
        [product["sku_id"] for product in comparison.get("products", [])], topic
    )
    evidence["product_names"] = {
        product["sku_id"]: product["name"]
        for product in comparison.get("products", [])
    }
    comparison["review_evidence"] = evidence
    return comparison


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def find_products(
    product_names: Iterable[str], catalog: Iterable[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Resolve explicit names/SKU IDs without fuzzy or semantic guessing."""
    catalog_list = list(catalog)
    resolved: List[Dict[str, Any]] = []
    seen = set()
    for requested in product_names:
        target = _normalized(requested)
        match = next(
            (
                sku
                for sku in catalog_list
                if target in {_normalized(sku["name"]), _normalized(sku["sku_id"])}
            ),
            None,
        )
        if match is not None and match["sku_id"] not in seen:
            resolved.append(match)
            seen.add(match["sku_id"])
    return resolved


def _product_facts(product: Dict[str, Any]) -> Dict[str, Any]:
    return {field: product[field] for field in PRODUCT_FACT_FIELDS if field in product}


def build_comparison(
    product_names: Iterable[str], catalog: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    requested = list(product_names)
    products = find_products(requested, catalog)
    return {
        "intent": "compare",
        "authoritative_source": AUTHORITATIVE_SOURCES["product_facts"],
        "requested_products": requested,
        "products": [_product_facts(product) for product in products],
        "missing_products": [
            name
            for name in requested
            if not find_products([name], products)
        ],
    }


def build_product_fact(
    product_names: Iterable[str],
    attribute: Optional[str],
    catalog: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    requested = list(product_names)
    products = find_products(requested, catalog)
    product = products[0] if products else None
    verified = bool(
        product is not None
        and attribute
        and attribute in product
        and attribute != "unknown"
    )
    return {
        "intent": "product_question",
        "authoritative_source": AUTHORITATIVE_SOURCES["product_facts"],
        "requested_products": requested,
        "product": _product_facts(product) if product else None,
        "attribute": attribute,
        "verified": verified,
        "value": product[attribute] if verified else None,
    }


def build_service_fact(
    product_names: Iterable[str],
    catalog: Iterable[Dict[str, Any]],
    *,
    service_attribute: Optional[str],
    fallback_product: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    requested = list(product_names)
    if service_attribute != "haul_away":
        return {
            "intent": "service_question",
            "authoritative_source": AUTHORITATIVE_SOURCES["service_eligibility"],
            "service": service_attribute,
            "verified": False,
        }
    products = find_products(requested, catalog)
    product = products[0] if products else fallback_product
    if product is not None:
        verified = "haul_away_CA_available" in product
        return {
            "intent": "service_question",
            "authoritative_source": AUTHORITATIVE_SOURCES["service_eligibility"],
            "service": "haul_away",
            "region": "CA",
            "scope": "product",
            "product": _product_facts(product),
            "verified": verified,
            "available": product.get("haul_away_CA_available") if verified else None,
        }

    catalog_list = list(catalog)
    eligible = [
        {"sku_id": sku["sku_id"], "name": sku["name"]}
        for sku in catalog_list
        if sku.get("haul_away_CA_available") is True
    ]
    represented = any("haul_away_CA_available" in sku for sku in catalog_list)
    return {
        "intent": "service_question",
        "authoritative_source": AUTHORITATIVE_SOURCES["service_eligibility"],
        "service": "haul_away",
        "region": "CA",
        "scope": "catalog",
        "verified": represented,
        "eligible_products": eligible,
    }


def render_comparison(result: Dict[str, Any]) -> str:
    return comparison_fallback(result)


def render_product_fact(result: Dict[str, Any]) -> str:
    return product_fact_fallback(result)


def render_service_fact(result: Dict[str, Any]) -> str:
    return service_fact_fallback(result)


def render_review_fact(result: Dict[str, Any]) -> str:
    return review_fallback(result)
