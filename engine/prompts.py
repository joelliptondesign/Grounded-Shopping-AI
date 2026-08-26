"""Small, dependency-free loader for versioned prompt files."""

from functools import lru_cache
from pathlib import Path


PROMPT_DIRECTORY = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load one UTF-8 Markdown prompt by filename from ``prompts/``."""
    if not name.endswith(".md") or Path(name).name != name:
        raise ValueError("prompt name must be a Markdown filename")
    path = PROMPT_DIRECTORY / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Prompt file not found: {path}") from error


def load_customer_prompt(task_prompt: str) -> str:
    """Compose task instructions with the shared customer conversation guide."""
    return f"{load_prompt(task_prompt)}\n\n{load_prompt('conversational_shopping_voice.md')}"
