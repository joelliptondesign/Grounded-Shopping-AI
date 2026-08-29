"""Deterministic mattress eligibility filtering and preference-aware ranking."""


SEMANTIC_PRIORITY_WEIGHTS = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "critical": 4.0,
}

# These are the normalized Phase 2 defaults exposed to callers.
DEFAULT_RANKING_WEIGHTS = {
    "price": 0.0,
    "firmness": 0.25,
    "support": 0.35,
    "cooling": 0.20,
    "motion_isolation": 0.20,
}

# Raw defaults share the semantic scale: low=1, medium=2, high=3, critical=4.
# Their 10-unit total normalizes to DEFAULT_RANKING_WEIGHTS exactly.
DEFAULT_RAW_RANKING_WEIGHTS = {
    "price": 0.0,
    "firmness": 2.5,
    "support": 3.5,
    "cooling": 2.0,
    "motion_isolation": 2.0,
}


def semantic_priority_weight(priority):
    """Map one constrained semantic priority to its inspectable numeric value."""
    try:
        return SEMANTIC_PRIORITY_WEIGHTS[priority]
    except KeyError as exc:
        raise ValueError(f"Unsupported priority level: {priority!r}") from exc


def normalized_ranking_weights(user_preferences):
    """Return normalized weights after applying explicit semantic overrides.

    Unspecified dimensions retain the original fixed-weight scorer's defaults.
    Price remains inactive by default so existing recommendations are preserved.
    """
    raw_weights = dict(DEFAULT_RAW_RANKING_WEIGHTS)
    for dimension, priority in user_preferences.get("priorities", {}).items():
        if dimension in raw_weights and priority is not None:
            raw_weights[dimension] = semantic_priority_weight(priority)

    total = sum(raw_weights.values())
    if total <= 0:
        raise ValueError("At least one ranking dimension must have a positive weight")
    return {dimension: weight / total for dimension, weight in raw_weights.items()}


def latex_constraint_active(user_preferences):
    """Return the structured latex constraint without inspecting raw query text."""
    return user_preferences.get("exclude_latex") is True


def constraint_evidence(user_preferences, sku):
    """Separate known hard-constraint failures from unavailable evidence."""
    violations = []
    unknowns = []

    requested_size = user_preferences.get("requested_size")
    if requested_size is not None:
        if sku.get("available_sizes") is None:
            unknowns.append("unknown_size_constraint")
        elif requested_size not in sku["available_sizes"]:
            violations.append("size_constraint")

    max_price = user_preferences.get("max_price")
    if max_price is not None:
        if sku.get("price") is None:
            unknowns.append("unknown_max_price")
        elif sku["price"] > max_price:
            violations.append("max_price")

    if latex_constraint_active(user_preferences):
        if sku.get("contains_latex") is None:
            unknowns.append("unknown_latex_constraint")
        elif sku["contains_latex"] is True:
            violations.append("latex_constraint")

    if user_preferences.get("require_CA_haul_away") is True:
        if sku.get("haul_away_CA_available") is None:
            unknowns.append("unknown_require_CA_haul_away")
        elif sku["haul_away_CA_available"] is not True:
            violations.append("require_CA_haul_away")

    return violations, unknowns


def constraint_violations(user_preferences, sku):
    """Return known violations plus unknown evidence that blocks safe eligibility."""
    violations, unknowns = constraint_evidence(user_preferences, sku)
    return violations + unknowns


def hard_gate(user_preferences, sku):
    return not constraint_violations(user_preferences, sku)


def service_gate(user_preferences, sku):
    """Compatibility wrapper for callers of the former separate service gate."""
    if user_preferences.get("require_CA_haul_away") is True:
        return sku.get("haul_away_CA_available") is True
    return True


def _price_score(user_preferences, sku):
    """Score affordability without turning a price preference into eligibility."""
    if sku.get("price") is None:
        return None
    price = max(0.0, float(sku["price"]))
    reference_price = user_preferences.get("budget_target")
    if reference_price is None:
        reference_price = user_preferences.get("max_price")
    if reference_price is None:
        reference_price = 2000.0
    reference_price = max(1.0, float(reference_price))
    return max(0.0, 1.0 - (price / reference_price))


def score_dimensions(user_preferences, sku):
    """Return the deterministic 0-1 utility for every ranking dimension."""

    targets = {
        "firmness": user_preferences.get("firmness_preference", 5),
        "support": user_preferences.get("support_preference", 5),
        "cooling": user_preferences.get("cooling_preference", 5),
        "motion_isolation": user_preferences.get("motion_isolation_preference", 5),
    }

    dimensions = {"price": _price_score(user_preferences, sku)}
    directions = user_preferences.get("directions", {})
    explicit_targets = {
        "firmness": "firmness_preference" in user_preferences,
        "support": "support_preference" in user_preferences,
        "cooling": "cooling_preference" in user_preferences,
        "motion_isolation": "motion_isolation_preference" in user_preferences,
    }
    for metric in ("firmness", "support", "cooling", "motion_isolation"):
        raw_value = sku.get(metric)
        if raw_value is None:
            dimensions[metric] = None
            continue
        value = float(raw_value)
        direction = directions.get(metric)
        if direction and not explicit_targets[metric]:
            dimensions[metric] = value / 10.0 if direction == "higher" else (10.0 - value) / 10.0
        else:
            target = float(targets[metric])
            dimensions[metric] = max(0.0, 10.0 - abs(value - target)) / 10.0
    return dimensions


def preference_tradeoffs(user_preferences, sku):
    """Return deterministic deviations from ordinary shopping preferences."""
    tradeoffs = []
    budget = user_preferences.get("budget_target")
    price = sku.get("price")
    if budget is not None and price is not None and price > budget:
        tradeoffs.append(
            {
                "type": "above_preferred_budget",
                "amount": price - budget,
                "label": f"${price - budget:,.0f} above your preferred budget",
            }
        )
    if user_preferences.get("prefer_CA_haul_away") is True:
        if "haul_away_CA_available" not in sku:
            tradeoffs.append(
                {
                    "type": "haul_away_unknown",
                    "label": "Haul-away availability isn't confirmed",
                }
            )
        elif sku.get("haul_away_CA_available") is not True:
            tradeoffs.append(
                {"type": "no_haul_away", "label": "Doesn't include California haul-away"}
            )
    return tradeoffs


def preference_misses(user_preferences, sku):
    """Return tradeoffs outside the shopper's stated flexibility."""
    flex_max = user_preferences.get("budget_flex_max")
    misses = []
    for item in preference_tradeoffs(user_preferences, sku):
        if (
            item["type"] == "above_preferred_budget"
            and flex_max is not None
            and sku.get("price") is not None
            and sku["price"] <= flex_max
        ):
            continue
        misses.append(item)
    return misses


def _near_match_penalty(user_preferences, sku):
    penalty = 0.0
    budget = user_preferences.get("budget_target")
    for item in preference_tradeoffs(user_preferences, sku):
        if item["type"] == "above_preferred_budget":
            penalty += min(0.5, item["amount"] / max(float(budget or 1), 1.0))
        elif item["type"] == "no_haul_away":
            penalty += 0.2
        else:
            penalty += 0.25
    return penalty


def score_sku(user_preferences, sku):
    weights = normalized_ranking_weights(user_preferences)
    dimensions = score_dimensions(user_preferences, sku)
    represented = {
        metric: value for metric, value in dimensions.items() if value is not None
    }
    represented_weight = sum(weights[metric] for metric in represented)
    if represented_weight <= 0:
        return 0.0
    return sum(
        value * weights[metric] for metric, value in represented.items()
    ) / represented_weight


def filter_eligible_skus(user_preferences, catalog):
    """Filter before ranking and retain per-SKU exclusion reasons."""
    eligible = []
    excluded = []

    for sku in catalog:
        violations, unknowns = constraint_evidence(user_preferences, sku)
        if violations or unknowns:
            item = {"sku_id": sku.get("sku_id"), "violations": violations}
            if unknowns:
                item["unknowns"] = unknowns
            excluded.append(item)
        else:
            eligible.append(sku)

    return eligible, excluded


def _scored_eligible_skus(user_preferences, eligible_skus):
    ranked = [
        (score_sku(user_preferences, sku) - _near_match_penalty(user_preferences, sku), sku)
        for sku in eligible_skus
    ]

    ranked.sort(
        key=lambda item: (
            bool(preference_misses(user_preferences, item[1])),
            -item[0],
            item[1]["sku_id"],
        )
    )
    return ranked


def _rank_eligible_skus(user_preferences, eligible_skus):
    return [item[1] for item in _scored_eligible_skus(user_preferences, eligible_skus)]


def rank_skus(user_preferences, catalog):
    eligible, _ = filter_eligible_skus(user_preferences, catalog)
    return _rank_eligible_skus(user_preferences, eligible)


def _active_hard_constraints(user_preferences):
    return {
        "requested_size": user_preferences.get("requested_size"),
        "max_price": user_preferences.get("max_price"),
        "exclude_latex": latex_constraint_active(user_preferences),
        "require_CA_haul_away": user_preferences.get("require_CA_haul_away") is True,
    }


def _previous_ranks(previous_ranked_candidates):
    return {
        candidate.get("sku_id"): rank
        for rank, candidate in enumerate(previous_ranked_candidates or [], start=1)
    }


def evaluate_decision(user_preferences, catalog, *, previous_decision_result=None):
    eligible, excluded = filter_eligible_skus(user_preferences, catalog)
    scored = _scored_eligible_skus(user_preferences, eligible)
    ranked = [item[1] for item in scored]
    candidate_count = len(ranked)
    previous_result = previous_decision_result or {}
    previous_ranks = _previous_ranks(previous_result.get("ranked_candidates"))
    weights = normalized_ranking_weights(user_preferences)
    candidate_scores = []
    for current_rank, (score, sku) in enumerate(scored, start=1):
        candidate_scores.append(
            {
                "sku_id": sku.get("sku_id"),
                "score": round(score, 6),
                "previous_rank": previous_ranks.get(sku.get("sku_id")),
                "current_rank": current_rank,
            }
        )

    metadata = {
        "haul_away_requested": user_preferences.get("require_CA_haul_away") is True,
        "zip_code": user_preferences.get("zip_code"),
        "candidate_count": candidate_count,
        "active_hard_constraints": _active_hard_constraints(user_preferences),
        "excluded_candidates": excluded,
        "active_normalized_weights": weights,
        "candidate_scores": candidate_scores,
        "preference_tradeoffs": {
            sku.get("sku_id"): preference_tradeoffs(user_preferences, sku)
            for sku in ranked
        },
        "exact_match_count": sum(
            not preference_misses(user_preferences, sku) for sku in ranked
        ),
        "previous_selected_sku_id": (
            previous_result.get("selected_sku") or {}
        ).get("sku_id"),
        "previous_active_normalized_weights": previous_result.get("metadata", {}).get(
            "active_normalized_weights"
        ),
    }

    if not ranked:
        violations = sorted(
            {
                violation
                for item in excluded
                for violation in item["violations"] + item.get("unknowns", [])
            }
        )
        return {
            "decision": "BLOCK",
            "reason": "no_valid_sku",
            "violations": violations,
            "selected_sku": None,
            "action": {
                "type": "no_recommendation",
                "status": "blocked",
                "sku_id": None,
            },
            "ranked_candidates": [],
            "metadata": metadata,
        }

    selected_sku = ranked[0]
    metadata["selected_sku_id"] = selected_sku.get("sku_id")
    is_near_match = metadata["exact_match_count"] == 0 and bool(
        metadata["preference_tradeoffs"].get(selected_sku.get("sku_id"))
    )
    return {
        "decision": "ALLOW",
        "reason": "near_match_recommendation" if is_near_match else "valid_recommendation",
        "violations": [],
        "selected_sku": selected_sku,
        "action": {
            "type": "recommendation",
            "status": "ready",
            "sku_id": selected_sku.get("sku_id"),
        },
        "ranked_candidates": ranked,
        "metadata": metadata,
        "match_type": "near_match" if is_near_match else "exact_or_ranked",
    }


def select_top_sku(user_preferences, catalog):
    decision_result = evaluate_decision(user_preferences, catalog)
    if decision_result["decision"] == "BLOCK":
        violations = decision_result["violations"]
        if violations == ["require_CA_haul_away"]:
            return {
                "message": "No available SKU satisfies the California haul-away requirement.",
                "constraint": "service",
            }
        if violations == ["latex_constraint"]:
            return {
                "message": "No available SKU satisfies the latex constraint.",
                "constraint": "latex",
            }
        raise ValueError("No SKU satisfies hard constraints: " + ", ".join(violations))
    return decision_result["selected_sku"]
