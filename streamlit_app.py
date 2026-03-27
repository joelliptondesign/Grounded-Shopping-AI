import os

from dotenv import load_dotenv
import streamlit as st

from engine.baseline_llm import get_baseline_recommendation
from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision, latex_constraint_active
from engine.explanation_llm import get_explanation


PRESET_SCENARIOS = {
    "High Cooling Performance Under Budget": {
        "query_text": "Looking for a high-performance hybrid mattress under $1500 for side sleepers. Cooling and motion isolation are top priorities. Prefer medium firmness around 6/10.",
        "max_price": 1500,
        "firmness_preference": 6,
        "cooling_preference": 8,
        "motion_isolation_preference": 8,
    },
    "Haul-Away Required": {
        "query_text": "Do these mattresses on Amazon include room-of-choice delivery, in-home setup, or haul-away service?",
        "max_price": 1500,
        "firmness_preference": 6,
        "cooling_preference": 8,
        "motion_isolation_preference": 8,
    },
    "Impossible Cooling Spec": {
        "query_text": "I’m looking for a medium-feel mattress (around 5/10 firmness) that sleeps very cool — ideally top-tier cooling. My budget is under $1000.",
        "max_price": 1000,
        "firmness_preference": 5,
        "cooling_preference": 9,
        "motion_isolation_preference": 7,
    },
}

GOVERNANCE_KEYWORDS = (
    "mattress",
    "sleep",
    "firmness",
    "cooling",
    "motion",
    "budget",
    "trial",
    "allergy",
    "latex",
)

GOVERNANCE_MESSAGE = (
    "This demonstration is scoped to structured mattress recommendation scenarios. "
    "Please adjust your query accordingly."
)


def build_user_preferences(max_price, desired_firmness, desired_cooling, desired_motion_isolation):
    return {
        "max_price": max_price,
        "firmness_preference": desired_firmness,
        "support_preference": 7,
        "cooling_preference": desired_cooling,
        "motion_isolation_preference": desired_motion_isolation,
    }


def query_in_scope(query_text):
    lowered = query_text.lower()
    return any(keyword in lowered for keyword in GOVERNANCE_KEYWORDS)


def build_explanation_facts(user_preferences, decision_result):
    selected_sku = decision_result.get("selected_sku")
    latex_applied = latex_constraint_active({"query_text": user_preferences["query_text"]})
    return {
        "selected_sku_id": selected_sku.get("sku_id") if selected_sku else None,
        "selected_name": selected_sku.get("name") if selected_sku else None,
        "selected_price": selected_sku.get("price") if selected_sku else None,
        "haul_away_CA_available": selected_sku.get("haul_away_CA_available") if selected_sku else None,
        "user_preferences": user_preferences,
        "selection_method": "hard_gate_then_weighted_score_then_stable_rank",
        "latex_constraint_applied": latex_applied,
        "decision": decision_result.get("decision"),
        "decision_reason": decision_result.get("reason"),
        "violations": decision_result.get("violations", []),
        "action": decision_result.get("action", {}),
        "metadata": decision_result.get("metadata", {}),
    }


def get_decision_explanation(user_preferences, decision_result):
    explanation_facts = build_explanation_facts(user_preferences, decision_result)
    explanation_text = get_explanation(
        decision_result.get("selected_sku"),
        explanation_facts,
        decision_result=decision_result,
    )

    if decision_result.get("decision") == "ALLOW" and explanation_facts["latex_constraint_applied"]:
        explanation_text = (
            "The selection excluded latex-containing products due to the stated allergy "
            "constraint.\n\n" + explanation_text
        )

    return explanation_text


def render_customer_outcome(decision_result):
    selected_sku = decision_result.get("selected_sku")

    if decision_result.get("decision") == "BLOCK":
        st.info("I couldn't find a mattress that matches all of those requirements.")
        return

    if selected_sku:
        st.success(f"Recommended mattress: {selected_sku.get('name')} ({selected_sku.get('sku_id')})")


def main():
    load_dotenv()
    st.set_page_config(page_title="Decision Layer Demo", layout="wide")
    st.title("Decision Layer Demo")
    st.caption("Side-by-side A/B comparison: Baseline LLM recommendation vs deterministic decision layer.")

    def sync_query_from_preset():
        preset_cfg = PRESET_SCENARIOS[st.session_state["selected_preset"]]
        st.session_state["query_text"] = preset_cfg["query_text"]

    st.sidebar.header("User Preferences")
    if st.session_state.get("selected_preset") == "California Haul-Away Required":
        st.session_state["selected_preset"] = "Haul-Away Required"
    selected_preset = st.sidebar.selectbox(
        "Scenario",
        options=list(PRESET_SCENARIOS.keys()),
        key="selected_preset",
        on_change=sync_query_from_preset,
    )
    preset_cfg = PRESET_SCENARIOS[selected_preset]
    if "query_text" not in st.session_state:
        st.session_state["query_text"] = preset_cfg["query_text"]
    st.sidebar.text_area("Query", key="query_text")

    user_preferences = build_user_preferences(
        max_price=preset_cfg["max_price"],
        desired_firmness=preset_cfg["firmness_preference"],
        desired_cooling=preset_cfg["cooling_preference"],
        desired_motion_isolation=preset_cfg["motion_isolation_preference"],
    )
    user_preferences["query_text"] = st.session_state["query_text"]
    if selected_preset == "Haul-Away Required":
        user_preferences["require_CA_haul_away"] = True
    else:
        user_preferences["require_CA_haul_away"] = False

    tabs = st.tabs(["A/B Demo", "Chat Prototype"])

    with tabs[0]:
        st.subheader("Shared SKU Catalog")
        st.dataframe(SKU_CATALOG, use_container_width=True)

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("### Baseline (LLM)")
            if st.button("Run baseline"):
                if not query_in_scope(st.session_state["query_text"]):
                    st.session_state["baseline_output"] = GOVERNANCE_MESSAGE
                    st.session_state["baseline_fallback"] = False
                else:
                    baseline_input = {
                        "query_text": st.session_state["query_text"],
                        "user_preferences": user_preferences,
                    }
                    st.session_state["baseline_output"] = get_baseline_recommendation(baseline_input, SKU_CATALOG)
                    if not os.getenv("OPENAI_API_KEY"):
                        st.session_state["baseline_fallback"] = True
                    else:
                        st.session_state["baseline_fallback"] = False

            if "baseline_output" in st.session_state:
                st.write(st.session_state["baseline_output"])
                if st.session_state.get("baseline_fallback"):
                    st.caption("Fallback mode active: OPENAI_API_KEY not set.")

        with col_right:
            st.markdown("### Decision Layer (Deterministic)")
            if st.button("Run decision layer"):
                if not query_in_scope(st.session_state["query_text"]):
                    st.session_state["decision_error"] = GOVERNANCE_MESSAGE
                    st.session_state.pop("decision_result", None)
                    st.session_state.pop("explanation_text", None)
                else:
                    decision_result = evaluate_decision(user_preferences, SKU_CATALOG)
                    st.session_state["decision_result"] = decision_result
                    st.session_state["explanation_text"] = get_decision_explanation(
                        user_preferences, decision_result
                    )
                    st.session_state.pop("decision_error", None)

            if "decision_error" in st.session_state:
                st.error(st.session_state["decision_error"])
            if "decision_result" in st.session_state:
                decision_result = st.session_state["decision_result"]
                price_exclusions_exist = False
                if user_preferences["max_price"] is not None:
                    price_exclusions_exist = any(
                        sku["price"] > user_preferences["max_price"] for sku in SKU_CATALOG
                    )

                latex_constraint_triggered = "latex_constraint" in decision_result.get("violations", [])

                if price_exclusions_exist or latex_constraint_triggered:
                    st.markdown("This recommendation reflects your preferences and stated constraints.")

                st.markdown("#### Outcome")
                render_customer_outcome(decision_result)
                st.markdown(st.session_state.get("explanation_text", ""))
                if st.checkbox("Show system details", value=False):
                    with st.expander("Review structured decision data"):
                        st.json(decision_result)

    with tabs[1]:
        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        for message in st.session_state["messages"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_input = st.chat_input("Ask about delivery or get a recommendation")

        if user_input is not None:
            st.session_state["messages"].append({"role": "user", "content": user_input})
            delivery_keywords = ("delivery", "setup", "haul", "remove", "room")

            if any(keyword in user_input.lower() for keyword in delivery_keywords):
                decision_result = evaluate_decision(user_preferences, SKU_CATALOG)
                assistant_response = get_decision_explanation(user_preferences, decision_result)
                st.session_state["messages"].append({"role": "assistant", "content": assistant_response})
            else:
                decision_result = evaluate_decision(user_preferences, SKU_CATALOG)
                assistant_response = get_decision_explanation(user_preferences, decision_result)
                st.session_state["messages"].append({"role": "assistant", "content": assistant_response})
            st.rerun()


if __name__ == "__main__":
    main()
