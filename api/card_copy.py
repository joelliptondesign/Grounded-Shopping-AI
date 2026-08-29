"""Turn the engine's structured card rationale into the prototype's card copy.

The engine emits selection reasons and tradeoffs as short schema-ish labels
("High cooling: 8/10", "Tradeoff: Higher-priced option") because it renders into
a table on the Streamlit surface.  The Claude Design card carries one short
conversational sentence beneath it instead — "Excellent cooling and motion
isolation. The strongest match for what you told me matters most."

This module reads those labels back into semantic facts and writes them out in
that voice.  It adds no claims: every clause traces to a reason or tradeoff the
engine already produced.  Customer-facing text never carries a schema label.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


DIMENSION_WORDS = {
    "cooling": "cooling",
    "motion isolation": "motion isolation",
    "motion_isolation": "motion isolation",
    "support": "support",
    "firmness": "firmness",
}

# Grounded restatement of the engine's 1-10 scores in the prototype's voice.
def _quality(score: float) -> str:
    if score >= 9:
        return "excellent"
    if score >= 7:
        return "strong"
    if score >= 5:
        return "solid"
    return "modest"


_DIMENSION_REASON = re.compile(
    r"^(?:high|strong|excellent)?\s*(cooling|motion isolation|support|firmness)\s*:\s*(\d+(?:\.\d+)?)\s*/\s*10$",
    re.IGNORECASE,
)
_IN_BUDGET = re.compile(r"^within your \$([\d,]+) maximum$", re.IGNORECASE)
_SIZE = re.compile(r"^available in (.+)$", re.IGNORECASE)
_SERVICE = re.compile(r"^(.+?):\s*(available|not available)$", re.IGNORECASE)

_VALUE_REASONS = {
    "good value",
    "lower-price option",
    "makes good use of your budget",
    "good use of your budget",
}
_OVERALL_REASONS = {
    "strong overall fit",
    "strong all-around option",
    "balanced fit",
}


def _classify(label: str) -> Tuple[str, Any]:
    """Read one engine reason label back into a semantic fact."""
    text = str(label).strip()
    lowered = text.casefold()

    match = _DIMENSION_REASON.match(text)
    if match:
        return "dimension", (DIMENSION_WORDS[match.group(1).casefold()], float(match.group(2)))
    if text.startswith("Review theme: "):
        return "review", text[len("Review theme: ") :]
    if lowered in _VALUE_REASONS:
        return "value", None
    if lowered in _OVERALL_REASONS:
        return "overall", None
    if lowered == "premium option":
        return "premium", None
    if lowered == "closest firmness fit":
        return "firmness_fit", None
    if lowered == "useful tradeoff option":
        return "tradeoff_option", None
    if lowered == "verified latex-free":
        return "latex_free", None
    match = _IN_BUDGET.match(text)
    if match:
        return "in_budget", match.group(1)
    match = _SIZE.match(text)
    if match:
        return "size", match.group(1)
    match = _SERVICE.match(text)
    if match:
        return "service", (match.group(1), match.group(2).casefold() == "available")
    return "other", text


def _strength_clause(dimensions: List[Tuple[str, float]]) -> Optional[str]:
    """"Excellent cooling and motion isolation" / "Excellent cooling and solid support"."""
    if not dimensions:
        return None
    ranked = sorted(dimensions, key=lambda item: -item[1])[:2]
    if len(ranked) == 1:
        name, score = ranked[0]
        return f"{_quality(score).capitalize()} {name}"
    (first, first_score), (second, second_score) = ranked
    if _quality(first_score) == _quality(second_score):
        return f"{_quality(first_score).capitalize()} {first} and {second}"
    return (
        f"{_quality(first_score).capitalize()} {first} "
        f"and {_quality(second_score)} {second}"
    )


_TRADEOFF_ABOVE_BUDGET = re.compile(r"^\$([\d,]+) above your preferred budget$", re.IGNORECASE)
_TRADEOFF_LOWER = re.compile(r"^(slightly lower|lower)\s+(.+)$", re.IGNORECASE)

# (lower, slightly lower) — the softener belongs inside the phrase, not in front.
_LOWER_PHRASES = {
    "cooling": (
        "it doesn't sleep as cool as the others",
        "it sleeps a little warmer than the others",
    ),
    "motion isolation": (
        "you'll feel more movement across the bed",
        "you'll feel a little more movement across the bed",
    ),
    "support": ("it gives up some support", "it gives up a little support"),
    "firmness": (
        "it's a different feel from the others",
        "it's a slightly different feel from the others",
    ),
}


def _tradeoff_clause(tradeoff: str) -> Optional[str]:
    """A "though …" clause, or None when the tradeoff is a sentence of its own."""
    text = str(tradeoff or "").strip()
    if not text:
        return None

    match = _TRADEOFF_ABOVE_BUDGET.match(text)
    if match:
        return f"though it's ${match.group(1)} above the budget you had in mind"
    if text.casefold() == "higher-priced option":
        # The engine means "priced above others in this set", not "over budget",
        # and more than one card can carry it — so the wording stays relative.
        return "though it's one of the pricier options here"
    match = _TRADEOFF_LOWER.match(text)
    if match:
        dimension = DIMENSION_WORDS.get(match.group(2).strip().casefold())
        phrases = _LOWER_PHRASES.get(dimension) if dimension else None
        if phrases:
            slightly = match.group(1).casefold() == "slightly lower"
            return f"though {phrases[1 if slightly else 0]}"
    if text.casefold() == "doesn't include california haul-away":
        return "though haul-away isn't included"
    if text.casefold() == "haul-away availability isn't confirmed":
        return "though haul-away isn't confirmed for your address"
    return None


def _sentence(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


ATTRIBUTE_DIMENSIONS = ("cooling", "motion_isolation", "support")


def _attribute_dimensions(product: Optional[Dict[str, Any]]) -> List[Tuple[str, float]]:
    """The product's own strongest scored dimensions, straight from the catalog."""
    if not product:
        return []
    scored = [
        (DIMENSION_WORDS[field], float(product[field]))
        for field in ATTRIBUTE_DIMENSIONS
        if isinstance(product.get(field), (int, float))
    ]
    return [item for item in sorted(scored, key=lambda item: -item[1]) if item[1] >= 7][:2]


def explanation(
    card: Dict[str, Any],
    state: Optional[Dict[str, Any]] = None,
    product: Optional[Dict[str, Any]] = None,
    *,
    index: int = 0,
) -> str:
    """One conversational sentence or two for beneath a recommendation card."""
    state = state or {}
    facts = [_classify(reason) for reason in card.get("why_it_matches", []) if reason]
    kinds = {kind for kind, _ in facts}
    dimensions = [value for kind, value in facts if kind == "dimension"]
    if not dimensions:
        # The engine cited no scored dimension for this card (it names one only
        # when the shopper made it a priority). Describe the product from its own
        # catalog values so the copy still says something specific.
        dimensions = _attribute_dimensions(product)
    reviews = [value for kind, value in facts if kind == "review"]

    lead = _strength_clause(dimensions)
    if lead is None:
        if "overall" in kinds:
            lead = (
                "The strongest overall match for what you've told me matters most"
                if index == 0
                else "A strong all-around option for what you've described"
            )
        elif "value" in kinds:
            lead = "It makes good use of your budget"
        elif "premium" in kinds:
            lead = "The most premium option of these"
        elif "firmness_fit" in kinds:
            lead = "The closest feel to what you described"
        elif "latex_free" in kinds:
            lead = "A verified latex-free build"
        elif "in_budget" in kinds:
            lead = "It lands inside your budget"
        else:
            lead = "A solid match for what you've described"
    elif "overall" in kinds:
        # Only the top card can be the strongest overall.
        lead += (
            ", and the strongest overall match for what you've described"
            if index == 0
            else ", and a strong all-around fit"
        )
    elif "value" in kinds:
        lead += ", and it makes good use of your budget"

    clause = _tradeoff_clause(card.get("tradeoff") or "")
    if clause:
        return _sentence(f"{lead}, {clause}")

    sentences = [_sentence(lead)]
    # A review-derived tradeoff is already conversational; keep it verbatim so the
    # copy stays grounded in what reviewers actually said.
    extra = card.get("tradeoff") or (reviews[0] if reviews else "")
    if extra and _sentence(extra) not in sentences:
        sentences.append(_sentence(extra))
    return " ".join(sentences)


BEST_FOR = {
    "cooling": "Best for cooling",
    "motion isolation": "Best for motion isolation",
    "support": "Best for support",
    "firmness": "Closest on feel",
}
ALSO_FOR = {
    "cooling": "Also great for cooling",
    "motion isolation": "Also great for motion isolation",
    "support": "Also strong on support",
    "firmness": "Closest on feel",
}
GENERIC_ROLES = (
    "Also worth a look",
    "Another option to consider",
    "Worth a look",
    "Also worth considering",
)


def _role_candidates(
    card: Dict[str, Any], index: int, product: Optional[Dict[str, Any]] = None
) -> List[str]:
    facts = [_classify(reason) for reason in card.get("why_it_matches", []) if reason]
    kinds = [kind for kind, _ in facts]
    dimensions = [value for kind, value in facts if kind == "dimension"]
    if not dimensions:
        dimensions = _attribute_dimensions(product)

    candidates: List[str] = []
    if "overall" in kinds:
        candidates.append("Best overall" if index == 0 else "Still the balanced pick")
    for name, _score in sorted(dimensions, key=lambda item: -item[1]):
        candidates.append(BEST_FOR[name] if index == 0 else ALSO_FOR[name])
        candidates.append(ALSO_FOR[name])
    if "value" in kinds:
        candidates.append("Better value")
    if "premium" in kinds:
        candidates.append("Premium pick")
    if "firmness_fit" in kinds:
        candidates.append("Closest on feel")
    if "latex_free" in kinds:
        candidates.append("Latex-free pick")
    candidates.extend(GENERIC_ROLES)
    return candidates


def assign_roles(
    cards: List[Dict[str, Any]],
    attributes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    """Distinct category headings above the cards, in the prototype's wording.

    The prototype gives each card its own category ("Best overall", "Also great
    for cooling", "Better value"), so two cards never share a heading even when
    the engine cites the same reason for both.
    """
    attributes = attributes or {}
    used: set = set()
    headings: List[str] = []
    for index, card in enumerate(cards):
        product = attributes.get(card.get("sku_id"))
        heading = next(
            (item for item in _role_candidates(card, index, product) if item not in used),
            f"Option {index + 1}",
        )
        used.add(heading)
        headings.append(heading)
    return headings
