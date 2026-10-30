"""Short-term conversation memory: recent turns passed to the router."""
from dataclasses import dataclass, field

MAX_TURNS = 6      # last 3 exchanges (user + assistant)
MAX_CHARS = 800    # per message, keeps the router prompt small


@dataclass
class Turn:
    role: str                                             # "user" or "assistant"
    content: str
    departments: list[str] = field(default_factory=list)  # who answered (assistant only)


def format_history(history: list[Turn] | None) -> str:
    """Formats recent turns as plain text for the router prompt."""
    if not history:
        return ""
    lines = []
    for turn in history[-MAX_TURNS:]:
        text = turn.content.strip()
        if turn.role == "assistant":
            # Keep the END of long answers: follow-up questions usually come last
            if len(text) > MAX_CHARS:
                text = "..." + text[-MAX_CHARS:]
            who = f"Support ({', '.join(turn.departments)})" if turn.departments else "Support"
        else:
            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + "..."
            who = "Employee"
        lines.append(f"{who}: {text}")
    return "\n\n".join(lines)