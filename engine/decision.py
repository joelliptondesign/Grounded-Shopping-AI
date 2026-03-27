LATEX_CONSTRAINT_PHRASES = (
    "latex allergy",
    "allergic to latex",
    "must not contain latex",
)


def latex_constraint_active(user_preferences):
    query_text = str(user_preferences.get("query_text", "")).lower()
    return any(phrase in query_text for phrase in LATEX_CONSTRAINT_PHRASES)


def hard_gate(user_preferences, sku):
    max_price = user_preferences.get("max_price")
    if max_price is not None and sku.get("price", 0) > max_price:
        return False
    if latex_constraint_active(user_preferences) and sku.get("contains_latex") is True:
        return False
    return True


def service_gate(user_preferences, sku):
    if user_preferences.get("require_CA_haul_away") is True:
        return sku.get("haul_away_CA_available", False) is True
    return True


def score_sku(user_preferences, sku):
    weights = {
        "firmness": 0.25,
        "support": 0.35,
        "cooling": 0.20,
        "motion_isolation": 0.20,
    }

    targets = {
        "firmness": user_preferences.get("firmness_preference", 5),
        "support": user_preferences.get("support_preference", 5),
        "cooling": user_preferences.get("cooling_preference", 5),
        "motion_isolation": user_preferences.get("motion_isolation_preference", 5),
    }

    score = 0.0
    for metric, weight in weights.items():
        value = float(sku.get(metric, 0))
        target = float(targets[metric])
        closeness = max(0.0, 10.0 - abs(value - target)) / 10.0
        score += closeness * weight

    return score


def rank_skus(user_preferences, catalog):
    ranked = []
    for sku in catalog:
        if hard_gate(user_preferences, sku) and service_gate(user_preferences, sku):
            ranked.append((score_sku(user_preferences, sku), sku))

    ranked.sort(key=lambda item: (-item[0], item[1]["sku_id"]))
    return [item[1] for item in ranked]


def _derive_block_reason(user_preferences):
    violations = []

    if user_preferences.get("require_CA_haul_away") is True:
        violations.append("require_CA_haul_away")

    if latex_constraint_active(user_preferences):
        violations.append("latex_constraint")

    if violations:
        return "no_valid_sku", violations

    return "no_valid_sku", []


def evaluate_decision(user_preferences, catalog):
    ranked = rank_skus(user_preferences, catalog)
    candidate_count = len(ranked)

    metadata = {
        "haul_away_requested": user_preferences.get("require_CA_haul_away") is True,
        "zip_code": user_preferences.get("zip_code"),
        "candidate_count": candidate_count,
    }

    if not ranked:
        reason, violations = _derive_block_reason(user_preferences)
        return {
            "decision": "BLOCK",
            "reason": reason,
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
    return {
        "decision": "ALLOW",
        "reason": "valid_recommendation",
        "violations": [],
        "selected_sku": selected_sku,
        "action": {
            "type": "recommendation",
            "status": "ready",
            "sku_id": selected_sku.get("sku_id"),
        },
        "ranked_candidates": ranked,
        "metadata": metadata,
    }


def select_top_sku(user_preferences, catalog):
    decision_result = evaluate_decision(user_preferences, catalog)
    if decision_result["decision"] == "BLOCK":
        if user_preferences.get("require_CA_haul_away") is True:
            return {
                "message": "No available SKU satisfies the California haul-away requirement.",
                "constraint": "service",
            }
        if latex_constraint_active(user_preferences):
            return {
                "message": "No available SKU satisfies the latex constraint.",
                "constraint": "latex",
            }
        raise ValueError("No SKU satisfies hard constraints.")
    return decision_result["selected_sku"]
