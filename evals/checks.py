import re
from dataclasses import dataclass, field

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage
from autogen_core.models import ChatCompletionClient
from pydantic import BaseModel

from data.state import reset_state  # noqa: F401  (re-exported for run_evals.py)
from evals.scenarios import Scenario
from orchestrator import SupportResponse
from agents.guards import narrates_action

# ---------- Deterministic checks ----------
GLOBAL_FORBIDDEN = ["it_admin", "i acknowledge", "dear employee"]

# "I'll create a ticket" with no ticket created = a promise the system can't keep
PROMISE_PATTERN = re.compile(
    r"\b(i['’]ll|i will|we['’]ll|we will)\s+(create|raise|open|log|file|escalate)\b",
    re.IGNORECASE,
)


@dataclass
class CheckResult:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_checks(s: Scenario, resp: SupportResponse) -> CheckResult:
    out = CheckResult()
    fail, warn = out.failures.append, out.warnings.append

    # Routing
    got = {r.task.department for r in resp.results}
    names = lambda depts: sorted(d.value for d in depts)
    if s.strict_departments and got != s.departments:
        fail(f"departments: expected {names(s.departments)}, got {names(got)}")
    elif not s.strict_departments and not s.departments <= got:
        fail(f"departments: missing {names(s.departments - got)}")
    if resp.routing.is_sensitive != s.sensitive:
        fail(f"sensitive: expected {s.sensitive}, got {resp.routing.is_sensitive}")
    if s.escalated is not None and resp.escalated != s.escalated:
        fail(f"escalated: expected {s.escalated}, got {resp.escalated}")

    # Agent health
    for r in resp.results:
        if r.status != "success":
            fail(f"{r.task.department.value} agent status: {r.status}")

    # Tool usage
    called = {r.task.department: {tc.name for tc in r.tool_calls} for r in resp.results}
    all_called = set().union(*called.values())
    for dept, tools in s.must_call.items():
        if missing := tools - called.get(dept, set()):
            fail(f"{dept.value} did not call {sorted(missing)}")
    for dept, tools in s.should_call.items():
        if missing := tools - called.get(dept, set()):
            warn(f"{dept.value} did not call {sorted(missing)} (covered by safety net)")
    if bad := s.must_not_call & all_called:
        fail(f"forbidden tools called: {sorted(bad)}")
    for tool_name, expected in s.tool_args_contain.items():
        args = [tc.arguments for r in resp.results for tc in r.tool_calls if tc.name == tool_name]
        if not any(expected.lower() in a.lower() for a in args):
            fail(f"{tool_name} was not called with '{expected}' (calls: {args or 'none'})")

    # Tickets
    ticket_depts = {t["department"] for t in resp.tickets}
    if s.no_tickets and resp.tickets:
        fail(f"expected no tickets, got {sorted(ticket_depts)}")
    if missing := s.tickets_include - ticket_depts:
        fail(f"missing tickets for {sorted(missing)}")

    # Answer text
    answer = resp.final_answer.lower()
    for text in s.answer_contains:
        if text.lower() not in answer:
            fail(f"answer missing '{text}'")
    for text in s.answer_not_contains + GLOBAL_FORBIDDEN:
        if text.lower() in answer:
            fail(f"answer contains forbidden '{text}'")
    if PROMISE_PATTERN.search(resp.final_answer) and not resp.tickets:
        fail("answer promises a future action, but no ticket was created")
    if narrates_action(resp.final_answer):
        fail("answer describes an action instead of reporting a completed one")
    for r in resp.results:
        if r.retried:
            warn(f"{r.task.department.value} needed a retry nudge to act")

    # Latency
    if resp.timings["total"] > s.max_seconds:
        warn(f"slow: {resp.timings['total']:.1f}s (budget {s.max_seconds:.0f}s)")

    tokens = resp.total_usage.total_tokens
    if tokens > s.max_tokens:
        warn(f"tokens: {tokens:,} (budget {s.max_tokens:,})")
    return out


# ---------- LLM judge ----------
class Verdict(BaseModel):
    passed: bool
    reason: str


JUDGE_PROMPT = """
You are a strict QA reviewer for an employee support desk. You receive the
employee's message, the support reply, and ONE criterion. Decide only whether the
reply satisfies that criterion, judging the reply exactly as written. Do not
assume anything not stated in it. Give a one-sentence reason.
""".strip()


async def judge(s: Scenario, resp: SupportResponse, client: ChatCompletionClient) -> Verdict:
    agent = AssistantAgent("judge_agent", model_client=client,
                           system_message=JUDGE_PROMPT, output_content_type=Verdict)
    task = (f"Employee message:\n{s.query}\n\n"
            f"Support reply:\n{resp.final_answer}\n\n"
            f"Criterion:\n{s.judge}")
    result = await agent.run(task=task)
    message = result.messages[-1]
    if isinstance(message, StructuredMessage) and isinstance(message.content, Verdict):
        return message.content
    return Verdict(passed=False, reason="Judge returned unexpected output")