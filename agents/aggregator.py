import logging

from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient

logger = logging.getLogger(__name__)

AGGREGATOR_PROMPT = """
You combine answers from several support departments into ONE reply to an employee.

## Rules
1. Keep every fact from the department answers exactly: numbers, dates, statuses,
   next steps and ticket IDs. Never add facts, promises or timelines of your own.
2. Open with one short, natural sentence that reflects what they asked about
   (e.g. "Here's an update on your VPN and leave request."). Never write
   "I acknowledge".
3. Then give one section per topic with a short bold label (e.g. **Laptop**,
   **Salary**), in the order given (most urgent first), a few sentences each.
4. If a department asked the employee a question, keep that question clearly visible.
5. Use plain department names (HR, IT, Payroll, Hardware, Facilities), never
   internal ids like "it_admin". No "Dear employee", no sign-off, no filler like
   "feel free to ask".
6. If there are system notes, include them in the reply.
""".strip()

SENSITIVE_AGGREGATOR_PROMPT = """
You write the reply to an employee who has raised a sensitive matter, such as
harassment, discrimination or a security breach. You receive the support answers;
turn them into ONE short, human reply.

## Structure
1. Your FIRST sentence acknowledges how they feel or how serious this is, in your
   own words. For example:
   - "I'm really sorry you're dealing with this, and thank you for telling us."
   - "I understand how worrying a possible account breach is."
   Never open with "Here's an update" or any status-report phrasing.
2. Then, in plain sentences with NO headings or bold labels, say what has been done:
   the escalation, the ticket ID, when a human specialist will contact them, and
   any protective steps taken (such as accounts being locked).
3. Only if there are other, unrelated topics, add them afterwards, each under a
   short bold label.

## Rules
- Keep every fact and ticket ID exactly. Never add promises, timelines or advice
  that are not in the answers.
- Never ask them to describe what happened, and never minimise or judge the concern.
- Use plain department names, never internal ids like "it_admin". No sign-off.
- If there are system notes, include them in the reply.
""".strip()


def _fallback_merge(parts: list[tuple[str, str]], notes: list[str]) -> str:
    """Plain merge used if the aggregator LLM call fails."""
    sections = [f"**{label}**\n{text}" for label, text in parts]
    sections += notes
    return "\n\n".join(sections)


async def aggregate(
    query: str,
    parts: list[tuple[str, str]],
    is_sensitive: bool,
    model_client: ChatCompletionClient,
    notes: list[str] | None = None,
) -> str:
    """Merges (department label, answer) pairs into one reply.
    A single non-sensitive answer with no notes is returned as-is, with no LLM call.
    Sensitive requests always go through the sensitive prompt for the right tone."""
    notes = notes or []
    if len(parts) == 1 and not notes and not is_sensitive:
        return parts[0][1]

    system_message = SENSITIVE_AGGREGATOR_PROMPT if is_sensitive else AGGREGATOR_PROMPT
    sections = "\n\n".join(f"### {label}\n{text}" for label, text in parts)
    task = f"Employee's message:\n{query}\n\nSupport answers:\n{sections}"
    if notes:
        task += "\n\nSystem notes (must be included):\n" + "\n".join(f"- {n}" for n in notes)

    agent = AssistantAgent("aggregator_agent", model_client=model_client,
                           system_message=system_message)
    try:
        result = await agent.run(task=task)
        text = result.messages[-1].content
        if isinstance(text, str) and text.strip():
            return text
    except Exception as exc:
        logger.exception("Aggregation failed: %s", exc)
    return _fallback_merge(parts, notes)