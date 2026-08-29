"""Local API that puts the existing shopping-agent engine behind Live mode.

This is an adapter, not a second agent.  Every turn runs through
``engine.conversation.process_conversation_turn`` and
``engine.conversational_response.generate_turn_response`` exactly as the
Streamlit surface runs them, and the result is restated in the frontend's block
contract by :mod:`api.blocks`.  No eligibility, ranking, grounding, recovery or
shopper-state logic lives here.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.blocks import more_blocks, turn_to_blocks
from api.turn_stream import sse, split_turn_payload
from api.more_like_this import additional_products, heading_for, record_presentation
from api.sessions import Session, SessionStore
from engine.conversation import process_conversation_turn
from engine.conversational_response import generate_turn_response
from engine.customer_copy import CONFIGURATION_FAILURE, ROUTING_FAILURE
from engine.data import SKU_CATALOG
from engine.timing import public_timing


logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_ENTRY = "/app/Rufus%20Shopping%20Agent.dc.html"

# Development-only. Never on by default: the normal response carries no
# reasoning traces or diagnostic payloads.
DEBUG_TURNS = os.getenv("LIVE_DEBUG") == "1"

NOTHING_MORE = (
    "That's everything I have that still fits what you're looking for. "
    "Widen the budget or ease up on one of your must-haves and I'll find more."
)

app = FastAPI(title="Grounded Shopping AI — Live mode", version="1.0")
store = SessionStore()


class SessionCreated(BaseModel):
    session_id: str


class TurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class TurnResponse(BaseModel):
    blocks: list
    products: list = []
    state_hint: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None


class MoreRequest(BaseModel):
    category: str = Field(default="", max_length=120)
    shown: List[str] = Field(default_factory=list, max_length=24)


def _elicitation_response(
    session: Session, message: str
) -> Optional[Dict[str, Any]]:
    """Route a tapped suggestion back through the engine's structured path.

    The frontend seam only carries text, so a suggested reply arrives as a
    message.  When it is verbatim one of the pending elicitation's options, the
    deterministic resolver handles it instead of re-extracting it with a model —
    preserving the structured elicitation semantics rather than bypassing them.
    """
    pending = session.pending_elicitation()
    if not pending:
        return None
    typed = message.strip().casefold()
    for option in pending.get("options", []):
        if str(option.get("label", "")).strip().casefold() == typed:
            return {
                "elicitation_id": pending.get("id"),
                "action": "select",
                "option_id": option.get("id"),
            }
    skip_label = pending.get("skip_label")
    if pending.get("allow_skip") and skip_label and skip_label.strip().casefold() == typed:
        return {"elicitation_id": pending.get("id"), "action": "skip"}
    return None


def _state_hint(session: Session) -> Dict[str, Any]:
    """What the shopper's state implies about the *next* turn.

    The frontend chooses its loading treatment before a turn starts, and the
    Claude Design prototype reserves the multi-step timeline for genuine
    multi-step shopping work. Reading that from the engine's own state — which
    basics are still outstanding, whether anything is on screen — keeps the
    decision grounded instead of guessed. It says nothing about pipeline stages.
    """
    state = session.preference_state
    hard = state.get("hard_constraints") or {}
    soft = state.get("soft_preferences") or {}
    missing = []
    if hard.get("size") is None:
        missing.append("size")
    if hard.get("max_price") is None and soft.get("budget_target") is None:
        missing.append("budget")
    return {
        "missing_basics": missing,
        "has_products": bool(state.get("recent_product_names")),
    }


def _debug_payload(turn: Dict[str, Any]) -> Dict[str, Any]:
    """Small, development-only summary. Not reasoning, not a full turn dump."""
    return {
        "intent": turn.get("intent"),
        "response_strategy": turn.get("response_strategy"),
        "modality": (turn.get("presentation") or {}).get("modality"),
        "recommendation_readiness": turn.get("recommendation_readiness"),
        "shopping_action_validation": turn.get("shopping_action_validation"),
        "pipeline_actions": turn.get("pipeline_actions"),
        "decision": (turn.get("decision_result") or {}).get("decision"),
        "generation": turn.get("generation_audit"),
        "latency": public_timing(turn.get("timing") or {}),
    }


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "catalog_size": len(SKU_CATALOG)}


@app.post("/api/session", response_model=SessionCreated)
def create_session() -> SessionCreated:
    return SessionCreated(session_id=store.create().session_id)


@app.delete("/api/session/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    store.delete(session_id)


def _run_turn(session: Session, message: str):
    """Run one turn's engine work. Shared verbatim by both turn endpoints.

    Returns either a finished ``TurnResponse`` (the failure paths) or
    ``(turn, generate)`` where ``generate`` produces the validated prose. The
    split exists so the streaming endpoint can send the structured result before
    calling ``generate``; the engine work itself is identical either way.
    """
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        return TurnResponse(
            blocks=[{"kind": "text", "parts": [{"t": CONFIGURATION_FAILURE}]}],
            error="model_unavailable",
        )

    history = session.history()
    try:
        turn = process_conversation_turn(
            message,
            session.preference_state,
            SKU_CATALOG,
            previous_decision_result=session.previous_decision_result,
            conversation_history=history,
            elicitation_response=_elicitation_response(session, message),
        )
    except Exception:
        logger.exception("conversation turn failed for session %s", session.session_id)
        return TurnResponse(
            blocks=[{"kind": "text", "parts": [{"t": CONFIGURATION_FAILURE}]}],
            error="engine_failure",
        )

    # Commit engine-owned state before generating prose, exactly as the
    # Streamlit surface does — the shopper's state advanced either way.
    session.preference_state = turn["preference_state"]
    if turn.get("decision_result") is not None:
        session.previous_decision_result = turn["decision_result"]

    if turn.get("response_text") is None:
        session.record(message, ROUTING_FAILURE)
        return TurnResponse(
            blocks=[{"kind": "text", "parts": [{"t": ROUTING_FAILURE}]}],
            error="routing_failure",
        )

    def generate() -> str:
        # Development-only diagnostics; gated behind LIVE_DEBUG like the rest.
        audit: Dict[str, Any] = {}
        try:
            reply = generate_turn_response(
                turn, message, history, catalog=SKU_CATALOG, audit=audit
            )
        except Exception:
            logger.exception("response generation failed for session %s", session.session_id)
            reply = turn["response_text"]
        turn["generation_audit"] = {
            "attempts": len(audit.get("attempts") or []),
            "fallback_used": audit.get("fallback_used"),
            "reasons": [r for a in (audit.get("attempts") or []) for r in a.get("reasons", [])],
        }
        return reply

    return turn, generate


@app.post("/api/session/{session_id}/turn", response_model=TurnResponse)
def take_turn(session_id: str, request: TurnRequest) -> TurnResponse:
    session = store.get(session_id)
    if session is None:
        # The frontend recreates a session and retries once on this.
        raise HTTPException(status_code=404, detail="unknown_session")
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="empty_message")

    with session.lock:
        result = _run_turn(session, message)
        if isinstance(result, TurnResponse):
            return result
        turn, generate = result
        reply = generate()
        payload = turn_to_blocks(
            turn, reply, previous_replies=session.last_replies, asked=message
        )
        session.last_replies = payload.get("replies") or []
        session.record(message, reply)

    return TurnResponse(
        blocks=payload["blocks"],
        products=payload["products"],
        state_hint=_state_hint(session),
        debug=_debug_payload(turn) if DEBUG_TURNS else None,
    )


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _turn_events(session: Session, message: str) -> Iterator[str]:
    """The same turn as `/turn`, delivered in the order it actually finishes.

    The structured result is validated and final when
    ``process_conversation_turn`` returns; the prose is not written until after
    that. Sending the structured half first lets it render while generation is
    still running. Nothing skips validation, no unvalidated tokens are emitted,
    and no internal stage is exposed — the loading treatment stays the
    frontend's decision, exactly as before.
    """
    with session.lock:
        result = _run_turn(session, message)
        if isinstance(result, TurnResponse):
            yield sse("message", {"block": result.blocks[0]})
            yield sse("complete", {"replies": [], "error": result.error})
            return

        turn, generate = result
        structure, products, _text, _replies = split_turn_payload(turn, None, asked=message)
        if structure:
            yield sse("presentation", {"blocks": structure, "products": products})

        reply = generate()
        _structure, _products, message_block, replies = split_turn_payload(
            turn, reply, session.last_replies, asked=message
        )
        session.last_replies = replies
        session.record(message, reply)

    yield sse("message", {"block": message_block})
    payload: Dict[str, Any] = {"replies": replies, "state_hint": _state_hint(session)}
    if DEBUG_TURNS:
        payload["debug"] = _debug_payload(turn)
    yield sse("complete", payload)


@app.post("/api/session/{session_id}/turn/stream")
def take_turn_stream(session_id: str, request: TurnRequest) -> StreamingResponse:
    """Progressive delivery of one turn. Identical engine path to `/turn`."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown_session")
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="empty_message")
    return StreamingResponse(
        _turn_events(session, message),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/session/{session_id}/more", response_model=TurnResponse)
def see_more(session_id: str, request: MoreRequest) -> TurnResponse:
    """The prototype's per-category "see more", answered by the real agent.

    No model call: the shopper's current decision result already holds every
    eligible, ranked candidate for their state, so this only surfaces more of
    what the engine has already admitted.
    """
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown_session")

    with session.lock:
        presentation, sku_ids, candidates = additional_products(
            session.previous_decision_result,
            session.preference_state,
            request.category,
            request.shown,
        )
        if presentation is None:
            return TurnResponse(
                blocks=[{"kind": "text", "parts": [{"t": NOTHING_MORE}]}],
                products=[],
            )
        payload = more_blocks(
            heading_for(request.category),
            presentation,
            session.preference_state,
            {item["sku_id"]: item for item in candidates if item.get("sku_id")},
        )
        if not payload["blocks"]:
            return TurnResponse(
                blocks=[{"kind": "text", "parts": [{"t": NOTHING_MORE}]}],
                products=[],
            )
        record_presentation(
            session.preference_state,
            list(request.shown),
            sku_ids,
            [item["name"] for item in payload["products"] if item.get("name")],
        )

    return TurnResponse(blocks=payload["blocks"], products=payload["products"])


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse(FRONTEND_ENTRY)


if FRONTEND_DIR.is_dir():
    # Same-origin static hosting keeps the prototype to one process and no CORS.
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
