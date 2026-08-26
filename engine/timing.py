"""Turn-level latency instrumentation using monotonic duration measurements."""

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional


TIMING_FIELDS = (
    "turn_started_at",
    "extraction_started_at",
    "extraction_completed_at",
    "decision_ready_at",
    "presentation_ready_at",
    "presentation_visible_at",
    "generation_started_at",
    "first_token_at",
    "generation_completed_at",
    "response_visible_at",
    "turn_completed_at",
)


def new_turn_timing() -> Dict[str, Any]:
    timing: Dict[str, Any] = {
        field: None for field in TIMING_FIELDS
    }
    timing.update(
        {
            "response_path": None,
            "generation_status": "not_started",
            "metrics_ms": {},
            "_monotonic": {},
        }
    )
    mark_timing(timing, "turn_started_at")
    return timing


def mark_timing(
    timing: Dict[str, Any], field: str, *, monotonic_value: Optional[float] = None
) -> None:
    """Record a wall timestamp while using a monotonic clock for all durations."""
    if field not in TIMING_FIELDS:
        raise ValueError(f"Unknown timing field: {field}")
    if timing.get(field) is not None:
        return
    timing[field] = datetime.now(timezone.utc).isoformat()
    timing.setdefault("_monotonic", {})[field] = (
        perf_counter() if monotonic_value is None else monotonic_value
    )
    _refresh_metrics(timing)


def set_response_path(
    timing: Dict[str, Any], path: str, *, generation_status: Optional[str] = None
) -> None:
    if path not in {"streamed", "buffered", "deterministic_fallback"}:
        raise ValueError(f"Unknown response path: {path}")
    timing["response_path"] = path
    if generation_status is not None:
        timing["generation_status"] = generation_status


def complete_turn(timing: Dict[str, Any]) -> None:
    mark_timing(timing, "turn_completed_at")


def public_timing(timing: Dict[str, Any]) -> Dict[str, Any]:
    """Return serializable developer metadata without private clock samples."""
    _refresh_metrics(timing)
    return {key: value for key, value in timing.items() if key != "_monotonic"}


def _refresh_metrics(timing: Dict[str, Any]) -> None:
    marks = timing.get("_monotonic", {})

    def duration(start: str, end: str) -> Optional[float]:
        if start not in marks or end not in marks:
            return None
        return round(max(0.0, marks[end] - marks[start]) * 1000, 3)

    visible_marks = [
        marks[field]
        for field in ("presentation_visible_at", "response_visible_at")
        if field in marks
    ]
    perceived = None
    if visible_marks and "turn_started_at" in marks:
        perceived = round(
            max(0.0, min(visible_marks) - marks["turn_started_at"]) * 1000, 3
        )

    timing["metrics_ms"] = {
        "extraction_latency": duration(
            "extraction_started_at", "extraction_completed_at"
        ),
        "decision_ready_latency": duration("turn_started_at", "decision_ready_at"),
        "presentation_ready_latency": duration(
            "turn_started_at", "presentation_ready_at"
        ),
        "generation_ttft": duration("generation_started_at", "first_token_at"),
        "generation_latency": duration(
            "generation_started_at", "generation_completed_at"
        ),
        "user_perceived_first_response_latency": perceived,
        "total_turn_latency": duration("turn_started_at", "turn_completed_at"),
    }
