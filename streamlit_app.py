import os

from dotenv import load_dotenv
import streamlit as st

from engine.baseline_llm import get_baseline_recommendation
from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response_stream
from engine.customer_copy import CONFIGURATION_FAILURE, ROUTING_FAILURE
from engine.data import SKU_CATALOG
from engine.decision import evaluate_decision, latex_constraint_active
from engine.explanation_llm import get_explanation
from engine.preference_extraction import new_preference_state
from engine.presentation import with_presentation_message
from engine.timing import mark_timing, public_timing


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
    latex_applied = latex_constraint_active(user_preferences)
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
        "decision_result": decision_result,
    }


def get_decision_explanation(
    user_preferences,
    decision_result,
    grounding_audit=None,
    approved_relaxation=None,
    conversation_context=None,
):
    explanation_facts = build_explanation_facts(user_preferences, decision_result)
    explanation_facts["approved_relaxation"] = approved_relaxation
    explanation_text = get_explanation(
        decision_result.get("selected_sku"),
        explanation_facts,
        decision_result=decision_result,
        catalog=SKU_CATALOG,
        grounding_audit=grounding_audit,
        conversation_context=conversation_context,
    )

    if decision_result.get("decision") == "ALLOW" and explanation_facts["latex_constraint_applied"]:
        explanation_text = (
            "The selection excluded latex-containing products due to the stated allergy "
            "constraint.\n\n" + explanation_text
        )

    return explanation_text


# The helpers above support only the historical A/B experiment. The primary
# shopping surface enters the current architecture through
# process_conversation_turn() below.


def render_customer_outcome(decision_result):
    selected_sku = decision_result.get("selected_sku")

    if decision_result.get("decision") == "BLOCK":
        st.info("I couldn't find a mattress that matches all of those requirements.")
        return

    if selected_sku:
        st.success(f"Recommended mattress: {selected_sku.get('name')} ({selected_sku.get('sku_id')})")


def _queue_quick_reply(reply):
    st.session_state["pending_quick_reply"] = reply


def _format_latency(value):
    if value is None:
        return "Not recorded"
    return f"{value / 1000:.2f} s" if value >= 1000 else f"{value:.0f} ms"


def render_turn_presentation(presentation, *, key_prefix, render_message=True):
    """Render the framework-independent turn contract with basic Streamlit UI."""
    modality = presentation.get("modality")

    if modality == "recommendation_cards":
        products = presentation.get("products", [])
        columns = st.columns(min(3, max(1, len(products))))
        for index, product in enumerate(products):
            with columns[index % len(columns)]:
                with st.container(border=True):
                    st.markdown(f"#### {product.get('name', 'Mattress')}")
                    if product.get("price") is not None:
                        st.markdown(f"**${product['price']:,.0f}**")
                    for reason in product.get("why_it_matches", []):
                        st.markdown(f"- {reason}")
                    if product.get("tradeoff"):
                        st.caption(f"Tradeoff: {product['tradeoff']}")
                    service = product.get("service_indicator")
                    if service:
                        status = "Available" if service.get("available") else "Not available"
                        st.caption(f"{service['label']}: {status}")

    elif modality == "comparison_table":
        comparison = presentation.get("comparison") or {}
        names = comparison.get("products", [])
        table_rows = []
        for row in comparison.get("rows", []):
            table_row = {"Attribute": row["label"]}
            for name, value in zip(names, row.get("values", [])):
                table_row[name] = value
            table_rows.append(table_row)
        if table_rows:
            st.dataframe(table_rows, hide_index=True, width="stretch")

    elif modality == "product_detail":
        products = presentation.get("products", [])
        if products:
            product = products[0]
            with st.container(border=True):
                st.markdown(f"#### {product.get('name', 'Mattress')}")
                for detail in product.get("details", []):
                    st.markdown(f"**{detail['label']}:** {detail['value']}")

    controls = presentation.get("actions") or []
    if not controls:
        controls = [
            {"label": label, "action": "suggested_reply"}
            for label in presentation.get("suggested_replies", [])
        ]
    if controls:
        columns = st.columns(min(3, len(controls)))
        for index, control in enumerate(controls):
            columns[index % len(columns)].button(
                control["label"],
                key=f"{key_prefix}_{index}_{control.get('action', 'reply')}",
                on_click=_queue_quick_reply,
                args=(control["label"],),
            )

    if render_message:
        st.markdown(presentation.get("message", ""))


def render_legacy_experiment():
    """Render the original prototype without leaking its controls into chat."""
    st.title("Original A/B Experiment")
    st.caption(
        "A preserved developer experiment comparing the original baseline and "
        "deterministic recommendation paths."
    )

    def sync_query_from_preset():
        preset_cfg = PRESET_SCENARIOS[st.session_state["selected_preset"]]
        st.session_state["query_text"] = preset_cfg["query_text"]

    st.sidebar.divider()
    st.sidebar.subheader("Experiment controls")
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

    st.subheader("Shared SKU Catalog")
    st.dataframe(SKU_CATALOG, width="stretch")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### Original baseline (LLM)")
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
        st.markdown("### Original deterministic decision layer")
        if st.button("Run decision layer"):
            if not query_in_scope(st.session_state["query_text"]):
                st.session_state["decision_error"] = GOVERNANCE_MESSAGE
                st.session_state.pop("decision_result", None)
                st.session_state.pop("explanation_text", None)
            else:
                decision_result = evaluate_decision(user_preferences, SKU_CATALOG)
                st.session_state["decision_result"] = decision_result
                grounding_audit = {}
                st.session_state["explanation_text"] = get_decision_explanation(
                    user_preferences, decision_result, grounding_audit
                )
                st.session_state["decision_grounding_audit"] = grounding_audit
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
                st.markdown("This recommendation reflects the experiment's configured inputs.")

            st.markdown("#### Outcome")
            render_customer_outcome(decision_result)
            st.markdown(st.session_state.get("explanation_text", ""))
            if st.checkbox("Show experiment details", value=False):
                with st.expander("Review structured decision data"):
                    st.json(decision_result)
                with st.expander("Review grounding and guardrail data"):
                    st.json(st.session_state.get("decision_grounding_audit", {}))


def render_shopping_agent():
    st.title("Mattress Shopping Agent")
    st.caption(
        "Tell me what you're looking for, what matters most, or what you "
        "don't like about your current mattress."
    )
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "preference_state" not in st.session_state:
        st.session_state["preference_state"] = new_preference_state()

    for message_index, message in enumerate(st.session_state["messages"]):
        with st.chat_message(message["role"]):
            if message["role"] == "assistant" and message.get("presentation"):
                render_turn_presentation(
                    message["presentation"], key_prefix=f"turn_{message_index}"
                )
            else:
                st.markdown(message["content"])

    if st.checkbox("Developer details", value=False):
        with st.expander("Current structured shopping state", expanded=True):
            st.json(st.session_state["preference_state"])
        latest_turn = st.session_state.get("chat_turn_debug")
        if latest_turn is not None:
            with st.expander("Latest intent routing", expanded=True):
                st.json(latest_turn)
            latency = latest_turn.get("latency") or {}
            metrics = latency.get("metrics_ms") or {}
            with st.expander("Latency", expanded=True):
                st.markdown(
                    "  \n".join(
                        [
                            f"**Extraction:** {_format_latency(metrics.get('extraction_latency'))}",
                            f"**Decision ready:** {_format_latency(metrics.get('decision_ready_latency'))}",
                            f"**Presentation ready:** {_format_latency(metrics.get('presentation_ready_latency'))}",
                            f"**First generated token:** {_format_latency(metrics.get('generation_ttft'))}",
                            f"**Generation complete:** {_format_latency(metrics.get('generation_latency'))}",
                            f"**First visible response:** {_format_latency(metrics.get('user_perceived_first_response_latency'))}",
                            f"**Total turn:** {_format_latency(metrics.get('total_turn_latency'))}",
                            f"**Response path:** {latency.get('response_path') or 'Not recorded'}",
                        ]
                    )
                )
        latest_decision = st.session_state.get("chat_decision_result")
        if latest_decision is not None:
            with st.expander("Latest deterministic ranking details", expanded=False):
                metadata = latest_decision.get("metadata", {})
                st.json(
                    {
                        "before_weights": metadata.get(
                            "previous_active_normalized_weights"
                        ),
                        "active_normalized_weights": metadata.get(
                            "active_normalized_weights"
                        ),
                        "candidate_scores": metadata.get("candidate_scores", []),
                        "deterministic_top_sku_id": metadata.get("selected_sku_id"),
                        "eligible_candidate_ids": [
                            item.get("sku_id")
                            for item in latest_decision.get("ranked_candidates", [])
                        ],
                        "agent_selection": (
                            st.session_state.get("chat_turn_debug") or {}
                        ).get("shopping_selection"),
                    }
                )

    queued_reply = st.session_state.pop("pending_quick_reply", None)
    user_input = queued_reply or st.chat_input(
        "What are you looking for in a mattress?"
    )

    if user_input is not None:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        assistant_presentation = None
        if not os.getenv("OPENAI_API_KEY"):
            assistant_response = CONFIGURATION_FAILURE
        else:
            try:
                turn = process_conversation_turn(
                    user_input,
                    st.session_state["preference_state"],
                    SKU_CATALOG,
                    previous_decision_result=st.session_state.get(
                        "chat_decision_result"
                    ),
                    conversation_history=st.session_state["messages"][:-1][-8:],
                )
                st.session_state["preference_state"] = turn["preference_state"]
                turn_debug = {
                    "classified_intent": turn["intent"],
                    "shopping_action": turn.get("shopping_action"),
                    "shopping_action_validation": turn.get(
                        "shopping_action_validation"
                    ),
                    "response_strategy": turn["response_strategy"],
                    "selected_modality": turn.get("modality"),
                    "modality_selection_reason": turn.get("modality_reason"),
                    "presentation_contract": turn.get("presentation"),
                    "structured_product_card_data": (
                        turn.get("presentation") or {}
                    ).get("products", []),
                    "comparison_row_selection": (
                        (turn.get("presentation") or {}).get("comparison") or {}
                    ).get("rows", []),
                    "suggested_replies_and_actions": {
                        "suggested_replies": (
                            turn.get("presentation") or {}
                        ).get("suggested_replies", []),
                        "actions": (turn.get("presentation") or {}).get(
                            "actions", []
                        ),
                    },
                    "display_grounding_sources": (
                        turn.get("presentation") or {}
                    ).get("grounding_sources", {}),
                    "grounding_data": turn["grounding_data"],
                    "grounding_evidence": turn.get("grounding_evidence"),
                    "shopping_selection": turn.get("shopping_selection"),
                    "review_evidence_debug": turn.get("review_debug"),
                    "scope_guardrail": turn.get("scope_guardrail"),
                    "recovery": turn.get("recovery"),
                    "previous_valid_state": turn.get(
                        "previous_preference_state"
                    ),
                    "updated_state": turn.get("updated_preference_state"),
                    "state_changes": turn.get("state_changes"),
                    "pipeline_actions": turn.get("pipeline_actions"),
                    "extraction_error": turn.get("extraction_error"),
                }
                if turn["decision_result"] is not None:
                    st.session_state["chat_decision_result"] = turn[
                        "decision_result"
                    ]
                if turn["response_text"] is not None:
                    response_audit = {}
                    with st.chat_message("assistant"):
                        if turn["presentation"]["modality"] != "conversation":
                            render_turn_presentation(
                                turn["presentation"],
                                key_prefix=f"current_{len(st.session_state['messages'])}",
                                render_message=False,
                            )
                            mark_timing(
                                turn["timing"], "presentation_visible_at"
                            )
                        assistant_response = st.write_stream(
                            generate_turn_response_stream(
                                turn,
                                user_input,
                                st.session_state["messages"],
                                catalog=SKU_CATALOG,
                                audit=response_audit,
                            )
                        )
                    turn_debug["response_audit"] = response_audit
                else:
                    assistant_response = ROUTING_FAILURE
                assistant_presentation = with_presentation_message(
                    turn["presentation"], assistant_response
                )
                turn_debug["latency"] = public_timing(turn["timing"])
                st.session_state["chat_turn_debug"] = turn_debug
            except Exception:
                assistant_response = CONFIGURATION_FAILURE
                assistant_presentation = None
        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": assistant_response,
                "presentation": assistant_presentation,
            }
        )
        st.rerun()


def main():
    load_dotenv()
    st.set_page_config(page_title="Mattress Shopping Agent", layout="wide")
    surface = st.sidebar.radio(
        "View",
        ("Shopping Agent", "Advanced / Experiments"),
        key="app_surface",
    )
    if surface == "Shopping Agent":
        render_shopping_agent()
    else:
        render_legacy_experiment()


if __name__ == "__main__":
    main()
