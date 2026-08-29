"""Server-Sent Events helpers for progressive delivery of one Live turn.

The engine stays transport-agnostic: nothing here reaches into it, and no
internal pipeline stage is exposed.  A turn is simply split at the one boundary
that already exists — the structured presentation is validated and final when
``process_conversation_turn`` returns, while the prose is written afterwards —
so the structured half can be sent first.

Whether a turn shows no loading state, dots, or the multi-step progress
timeline remains entirely the frontend's decision, exactly as before.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from api.blocks import turn_to_blocks


def sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def split_turn_payload(
    turn: Dict[str, Any],
    message: Optional[str],
    previous_replies: Optional[List[str]] = None,
    asked: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]], List[str]]:
    """Split one rendered turn into its structured half and its prose half.

    Built by calling :func:`api.blocks.turn_to_blocks` — the same function the
    buffered endpoint uses — so both paths produce byte-identical blocks and the
    choreography cannot drift between them. The text block is always first and
    the suggestion pills always last, matching the buffered payload exactly.
    """
    payload = turn_to_blocks(
        turn, message or "", previous_replies=previous_replies, asked=asked
    )
    blocks = payload["blocks"]
    text_block = blocks[0] if blocks and blocks[0].get("kind") == "text" else None
    # Everything between the message and the pills is structure — including a
    # section heading like "Options with haul-away", which belongs with its cards.
    structure = [
        block for block in blocks[1:] if block.get("kind") != "suggest"
    ]
    return structure, payload["products"], text_block, payload.get("replies") or []
