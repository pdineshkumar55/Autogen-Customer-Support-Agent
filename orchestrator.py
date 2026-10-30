import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from autogen_agentchat.messages import ToolCallExecutionEvent, ToolCallRequestEvent
from autogen_core.models import ChatCompletionClient

from agents.aggregator import aggregate
from agents.guards import RETRY_NUDGE, narrates_action
from agents.router import RoutedTask, RoutingDecision, route_query
from agents.specialists import create_specialist
from config import DEPARTMENTS, Settings, get_model_client
from memory import Turn, format_history
from tools.common import TICKETS, escalate_to_human, make_create_ticket
from usage import Usage, usage_from_client, usage_from_messages

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str], None] | None


# ---------- Result objects ----------
@dataclass
class ToolCall:
    name: str
    arguments: str
    result: str
    is_error: bool


@dataclass
class AgentResult:
    task: RoutedTask
    status: str                      # success | timeout | error
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    duration_s: float = 0.0
    retried: bool = False            # True if the narration guard had to nudge the agent
    usage: Usage = field(default_factory=Usage)


@dataclass
class SupportResponse:
    query: str
    employee_id: str
    routing: RoutingDecision
    results: list[AgentResult]
    final_answer: str
    tickets: list[dict]
    escalated: bool
    timings: dict[str, float]
    used_history: bool = False
    usage: dict[str, Usage] = field(default_factory=dict)   # routing / specialists / aggregation
    model: str = ""

    @property
    def parallel_speedup(self) -> float:
        """Sum of individual agent times divided by the actual wall-clock time."""
        wall = self.timings.get("specialists", 0)
        total = sum(r.duration_s for r in self.results)
        return total / wall if wall else 1.0

    @property
    def total_usage(self) -> Usage:
        return sum(self.usage.values(), Usage())

    @property
    def cost_usd(self) -> float | None:
        return self.total_usage.cost_usd(self.model)

    def as_turns(self) -> list[Turn]:
        """This exchange as conversation turns, for the next request's history."""
        departments = [DEPARTMENTS[r.task.department].label for r in self.results]
        return [Turn("user", self.query), Turn("assistant", self.final_answer, departments)]


# ---------- Helpers ----------
def _notify(progress: ProgressFn, message: str) -> None:
    if progress:
        try:
            progress(message)
        except Exception:  # a UI problem must never break the request
            logger.exception("Progress callback failed")


def _extract_tool_calls(messages: list) -> list[ToolCall]:
    """Pairs each tool call request with its execution result."""
    requests = {}
    calls = []
    for message in messages:
        if isinstance(message, ToolCallRequestEvent):
            for fc in message.content:
                requests[fc.id] = fc
        elif isinstance(message, ToolCallExecutionEvent):
            for res in message.content:
                fc = requests.get(res.call_id)
                calls.append(ToolCall(
                    name=fc.name if fc else getattr(res, "name", "unknown"),
                    arguments=fc.arguments if fc else "",
                    result=str(res.content),
                    is_error=bool(res.is_error),
                ))
    return calls


async def _run_specialist(task: RoutedTask, employee_id: str,
                          model_client: ChatCompletionClient,
                          progress: ProgressFn = None) -> AgentResult:
    """Runs one specialist with a timeout. Never raises: failures become a ticket.
    If the agent describes an action without doing it, it gets one nudge to act."""
    info = DEPARTMENTS[task.department]
    start = time.perf_counter()
    agent = create_specialist(task.department, model_client, employee_id)
    try:
        result = await asyncio.wait_for(agent.run(task=task.sub_query),
                                        timeout=Settings.AGENT_TIMEOUT_SECONDS)
        messages = list(result.messages)
        response = messages[-1].content
        retried = False

        # Guard: "Submitting now..." with no tool call means nothing happened.
        # The agent is stateful, so a follow-up run continues with full context.
        if isinstance(response, str) and narrates_action(response):
            _notify(progress, f"🔁 {info.label} described an action without doing it; retrying")
            retry = await asyncio.wait_for(agent.run(task=RETRY_NUDGE),
                                           timeout=Settings.AGENT_TIMEOUT_SECONDS)
            messages += retry.messages
            response = retry.messages[-1].content
            retried = True

        agent_result = AgentResult(
            task=task,
            status="success",
            response=response if isinstance(response, str) else str(response),
            tool_calls=_extract_tool_calls(messages),
            duration_s=time.perf_counter() - start,
            retried=retried,
            usage=usage_from_messages(messages),
        )
        _notify(progress, f"{info.icon} {info.label} finished in {agent_result.duration_s:.1f}s")
        return agent_result
    except asyncio.TimeoutError:
        status, reason = "timeout", f"no answer within {Settings.AGENT_TIMEOUT_SECONDS}s"
    except Exception as exc:
        logger.exception("%s agent failed: %s", task.department.value, exc)
        status, reason = "error", type(exc).__name__

    # Never lose a request: hand it to the team as a ticket
    ticket = make_create_ticket(task.department.value)(
        employee_id, f"[Auto] {task.sub_query} ({reason})", task.priority.value)
    _notify(progress, f"⚠️ {info.label} could not finish ({status}); ticket raised")
    return AgentResult(
        task=task,
        status=status,
        response=(f"I couldn't complete this automatically, so I've raised ticket "
                  f"{ticket.get('ticket_id', '(pending)')} and the team will follow up."),
        duration_s=time.perf_counter() - start,
    )


def _new_tickets(mark: int, employee_id: str) -> list[dict]:
    return [t for t in TICKETS[mark:] if t["employee_id"] == employee_id]


# ---------- Main entry point ----------
async def handle_query(query: str, employee_id: str,
                       history: list[Turn] | None = None,
                       progress: ProgressFn = None) -> SupportResponse:
    timings: dict[str, float] = {}
    total_start = time.perf_counter()
    ticket_mark = len(TICKETS)
    history_text = format_history(history)

    # One client per stage, so each stage's usage is exact
    router_client = get_model_client(temperature=0)   # deterministic classification
    worker_client = get_model_client()                 # shared by parallel specialists
    aggregator_client = get_model_client()
    try:
        # 1. Route (with conversation context, if any)
        _notify(progress, "🧭 Understanding your request...")
        t = time.perf_counter()
        routing = await route_query(query, router_client, history_text)
        timings["routing"] = time.perf_counter() - t
        labels = ", ".join(DEPARTMENTS[task.department].label for task in routing.tasks)
        _notify(progress, f"📋 Routed to: {labels}"
                          + (" (sensitive, a human will be involved)" if routing.is_sensitive else ""))

        # 2. Run all specialists in parallel
        t = time.perf_counter()
        results = list(await asyncio.gather(
            *(_run_specialist(task, employee_id, worker_client, progress)
              for task in routing.tasks)
        ))
        timings["specialists"] = time.perf_counter() - t

        # 3. Guarantee a human is involved for sensitive matters
        notes: list[str] = []
        escalated = any(tk["department"] == "human_escalation"
                        for tk in _new_tickets(ticket_mark, employee_id))
        if routing.is_sensitive and not escalated:
            esc = escalate_to_human(employee_id, f"Auto-escalated sensitive request: {routing.summary}")
            escalated = True
            notes.append(f"This has been escalated to a human specialist (ticket "
                         f"{esc['ticket_id']}). {esc['message']}")
            _notify(progress, "🚨 Escalated to a human specialist")

        # 4. Merge into one reply. For follow-ups like "yes", give the aggregator
        #    the resolved meaning, not just the bare word.
        if len(results) > 1 or notes or routing.is_sensitive:
            _notify(progress, "✍️ Combining answers...")
        request_text = query if not history_text else f"{query}\n(Meaning: {routing.summary})"
        t = time.perf_counter()
        parts = [(DEPARTMENTS[r.task.department].label, r.response) for r in results]
        final_answer = await aggregate(request_text, parts, routing.is_sensitive,
                                       aggregator_client, notes)
        timings["aggregation"] = time.perf_counter() - t

        # 5. Usage per stage, read from the clients before they are closed
        usage = {
            "routing": usage_from_client(router_client),
            "specialists": usage_from_client(worker_client,
                                             calls=sum(r.usage.calls for r in results)),
            "aggregation": usage_from_client(aggregator_client),
        }
    finally:
        await router_client.close()
        await worker_client.close()
        await aggregator_client.close()

    timings["total"] = time.perf_counter() - total_start
    return SupportResponse(
        query=query,
        employee_id=employee_id,
        routing=routing,
        results=results,
        final_answer=final_answer,
        tickets=_new_tickets(ticket_mark, employee_id),
        escalated=escalated,
        timings=timings,
        used_history=bool(history_text),
        usage=usage,
        model=Settings.MODEL_NAME,
    )