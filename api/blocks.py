"""Adapt the engine's presentation contract to the frontend's block contract.

``engine.presentation.build_turn_presentation`` already produces a deterministic,
renderer-independent payload — modality, message, products, comparison rows,
actions, suggested replies.  This module only restates that payload in the block
shapes the Claude Design renderer already understands.  It makes no shopping
decisions: no filtering, no ranking, no copy about products beyond relabelling
what the engine produced.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from api.card_copy import assign_roles, explanation
from api.suggestions import suggested_replies


MAX_SUGGESTED_REPLIES = 4
# A structured elicitation's options are the answer, so they get more room than
# generic suggested replies — and the skip affordance is never truncated away.
MAX_ELICITATION_OPTIONS = 6


def _money(price: Any) -> Tuple[str, str]:
    """Split an engine price into the dollars/cents the card renders separately."""
    if not isinstance(price, (int, float)):
        return "", ""
    dollars, cents = divmod(round(float(price) * 100), 100)
    return f"{dollars:,}", f"{cents:02d}"


def _text(message: str) -> Dict[str, Any]:
    """Split the engine's prose into the renderer's plain/bold text parts.

    The conversational prompt emits Markdown emphasis, which the Streamlit
    surface renders. The Claude Design text block has its own bold part type, so
    ``**...**`` maps onto that instead of reaching the shopper as asterisks.
    """
    # The prototype renders a comparison in its own table block, so a Markdown
    # table in the prose would say everything twice.
    prose = "\n".join(
        line for line in str(message).splitlines() if not line.lstrip().startswith("|")
    ).strip()
    parts = []
    for index, chunk in enumerate(re.split(r"\*\*(.+?)\*\*", prose or message)):
        if chunk:
            parts.append({"t": chunk, "b": True} if index % 2 else {"t": chunk})
    return {"kind": "text", "parts": parts or [{"t": message}]}


def _product_record(sku_id: str, name: str, price: Any) -> Dict[str, Any]:
    """Backend commerce truth for one product: identity, name, price.

    Nothing decorative belongs here.  The star rating, review count, imagery,
    Prime badge, delivery date and list-price line are presentation fixtures the
    frontend merges in by ``sku_id``; they never travel in either direction
    through the engine.
    """
    dollars, cents = _money(price)
    return {
        "id": sku_id,
        "short": name,
        "name": name,
        "price": price,
        "dollars": dollars,
        "cents": cents,
    }


def recommendation_blocks(
    presentation: Dict[str, Any],
    state: Dict[str, Any],
    attributes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Cards for the prototype's category treatment: a heading, a card, copy.

    ``attributes`` are the ranked candidates' catalog values, used only when the
    engine cited no scored dimension for a card, so the copy still describes the
    product from grounded numbers rather than falling back to a bland line.
    """
    attributes = attributes or {}
    cards = [card for card in presentation.get("products", []) if card.get("sku_id")]
    headings = assign_roles(cards, attributes)
    items: List[Dict[str, Any]] = []
    products: List[Dict[str, Any]] = []
    for index, (card, heading) in enumerate(zip(cards, headings)):
        sku_id = card["sku_id"]
        products.append(_product_record(sku_id, card.get("name") or sku_id, card.get("price")))
        items.append(
            {
                "id": sku_id,
                "role": heading,
                "why": explanation(card, state, attributes.get(sku_id), index=index),
            }
        )
    return items, products


def _ranked_attributes(turn: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        candidate["sku_id"]: candidate
        for candidate in (turn.get("decision_result") or {}).get("ranked_candidates", [])
        if candidate.get("sku_id")
    }


def _comparison_block(
    presentation: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    comparison = presentation.get("comparison") or {}
    names = comparison.get("products") or []
    # The prototype's comparison is a two-product table. When the engine resolves
    # a different number the prose answers it on its own, which is what the
    # prototype does for questions like "Which sleeps coolest?".
    if len(names) != 2:
        return None, []
    rows = [
        {
            "label": row.get("label", ""),
            "a": (row.get("values") or ["", ""])[0],
            "b": (row.get("values") or ["", ""])[1],
        }
        for row in comparison.get("rows", [])
    ]
    products = [
        _product_record(item["sku_id"], item.get("name") or item["sku_id"], None)
        for item in presentation.get("products", [])
        if item.get("sku_id")
    ]
    pair = [item["id"] for item in products][:2]
    # Imagery comes from the frontend's presentation fixtures, keyed by sku_id.
    block = {"kind": "compare", "pair": pair, "names": names[:2], "rows": rows}
    return block, products


def _detail_block(
    presentation: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Product detail reuses the existing service block: heading plus fact rows."""
    products = presentation.get("products") or []
    if not products:
        return None, []
    product = products[0]
    rows = [
        {"label": detail.get("label", ""), "value": detail.get("value", ""), "color": "#0f1111"}
        for detail in product.get("details", [])
    ]
    if not rows:
        return None, []
    block = {
        "kind": "service",
        "heading": product.get("name") or "Details",
        "rows": rows,
        "note": "From the product catalog for this item",
    }
    record = (
        [_product_record(product["sku_id"], product.get("name") or product["sku_id"], None)]
        if product.get("sku_id")
        else []
    )
    return block, record


def _engine_replies(presentation: Dict[str, Any]) -> List[str]:
    """Replies the engine itself specified: elicitation options, recovery actions."""
    elicitation = presentation.get("elicitation")
    if elicitation:
        labels = [
            option["label"]
            for option in elicitation.get("options", [])
            if option.get("label")
        ][:MAX_ELICITATION_OPTIONS]
        if elicitation.get("allow_skip") and elicitation.get("skip_label"):
            labels.append(elicitation["skip_label"])
        return labels
    return [
        reply for reply in presentation.get("suggested_replies") or [] if reply
    ][:MAX_SUGGESTED_REPLIES]


def turn_to_blocks(
    turn: Dict[str, Any],
    message: str,
    *,
    previous_replies: Optional[List[str]] = None,
    asked: Optional[str] = None,
) -> Dict[str, Any]:
    """Restate one engine turn as frontend blocks plus the products they name."""
    presentation = turn.get("presentation") or {}
    modality = presentation.get("modality")
    state = turn.get("preference_state") or {}

    blocks: List[Dict[str, Any]] = [_text(message)]
    products: List[Dict[str, Any]] = []

    if modality == "recommendation_cards":
        items, products = recommendation_blocks(
            presentation, state, _ranked_attributes(turn)
        )
        if items:
            # Service discovery introduces its list with its own bold heading,
            # as the prototype's haul-away flow does.
            heading = presentation.get("heading")
            if heading:
                blocks.append({"kind": "text", "parts": [{"t": heading, "b": True}]})
            # `more: False` keeps the prototype's per-category "see more" link.
            blocks.append({"kind": "recs", "items": items, "more": False})
    elif modality == "comparison_table":
        block, products = _comparison_block(presentation)
        if block:
            blocks.append(block)
    elif modality == "product_detail":
        block, products = _detail_block(presentation)
        if block:
            blocks.append(block)

    # The engine's own choices win: elicitation options and recovery actions are
    # part of the turn, not continuation suggestions.
    replies = _engine_replies(presentation)
    if not replies:
        replies = suggested_replies(
            modality,
            state,
            presentation.get("products") or [],
            previous=previous_replies,
            has_context=bool(state.get("recent_product_names") or products),
            service_discovery=bool(turn.get("service_discovery")),
            # A haul-away answer shouldn't be followed by the same offer again.
            service_answered=bool(turn.get("service_availability"))
            or turn.get("intent") == "service_question",
            asked=asked,
        )
    if replies:
        blocks.append({"kind": "suggest", "items": replies})

    return {"blocks": blocks, "products": products, "replies": replies}


def more_blocks(
    heading: str,
    presentation: Dict[str, Any],
    state: Dict[str, Any],
    attributes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """The prototype's "see more" result: a bold heading, then more cards.

    Mirrors ``moreFor()`` in the design source — a heading line followed by a
    second card list with no further "see more" link on it.
    """
    items, products = recommendation_blocks(presentation, state, attributes)
    if not items:
        return {"blocks": [], "products": []}
    return {
        "blocks": [
            {"kind": "text", "parts": [{"t": heading, "b": True}]},
            {"kind": "recs", "items": items, "more": True},
        ],
        "products": products,
    }
