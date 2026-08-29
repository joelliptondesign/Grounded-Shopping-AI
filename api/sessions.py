"""In-memory conversation sessions for the Live-mode prototype.

The shopping agent is multi-turn, so the API has to own exactly the state the
Streamlit surface owns in ``st.session_state``: the shopper's preference state,
the recent message history, and the previous decision result.  Nothing is
persisted — restarting the server drops every conversation, and the frontend
recreates a session when it sees an unknown id.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.preference_extraction import new_preference_state


# Enough headroom for a demo machine; oldest idle conversations are evicted first.
MAX_SESSIONS = 64
SESSION_TTL_SECONDS = 60 * 60 * 4
HISTORY_TURNS = 8


@dataclass
class Session:
    """One shopper conversation. Mirrors what the Streamlit session owns."""

    session_id: str
    preference_state: Dict[str, Any] = field(default_factory=new_preference_state)
    messages: List[Dict[str, str]] = field(default_factory=list)
    previous_decision_result: Optional[Dict[str, Any]] = None
    # Last set of continuation pills offered, so the next turn can vary them.
    last_replies: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    # Serialize turns within one conversation; engine state is not re-entrant.
    lock: threading.Lock = field(default_factory=threading.Lock)

    def history(self) -> List[Dict[str, str]]:
        """Prior turns only — the current user message is appended after the turn."""
        return self.messages[-HISTORY_TURNS:]

    def record(self, user_message: str, assistant_message: str) -> None:
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": assistant_message})
        self.last_used_at = time.time()

    def pending_elicitation(self) -> Optional[Dict[str, Any]]:
        return self.preference_state.get("pending_elicitation")


class SessionStore:
    """Process-local session registry. No database, by design."""

    def __init__(self, *, max_sessions: int = MAX_SESSIONS, ttl: float = SESSION_TTL_SECONDS):
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = ttl

    def create(self) -> Session:
        session = Session(session_id=uuid.uuid4().hex)
        with self._lock:
            self._evict()
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if time.time() - session.last_used_at > self._ttl:
                del self._sessions[session_id]
                return None
            session.last_used_at = time.time()
            return session

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def _evict(self) -> None:
        """Called with the store lock held."""
        now = time.time()
        for session_id, session in list(self._sessions.items()):
            if now - session.last_used_at > self._ttl:
                del self._sessions[session_id]
        while len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions.values(), key=lambda item: item.last_used_at)
            del self._sessions[oldest.session_id]
