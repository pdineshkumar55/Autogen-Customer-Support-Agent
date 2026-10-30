import logging
import re
from enum import Enum

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage
from autogen_core.models import ChatCompletionClient
from pydantic import BaseModel, Field

from config import Department, departments_for_prompt

logger = logging.getLogger(__name__)


# ---------- Output schema ----------
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2, Priority.CRITICAL: 3}


class RoutedTask(BaseModel):
    department: Department = Field(description="The department that handles this part.")
    sub_query: str = Field(
        description="A self-contained rewrite of this part of the request, written as "
                    "the employee would ask it, keeping every detail (dates, amounts, names), "
                    "including details from earlier in the conversation.")
    priority: Priority
    reason: str = Field(description="One short sentence on why this department.")


class RoutingDecision(BaseModel):
    tasks: list[RoutedTask]
    is_sensitive: bool = Field(
        description="True for harassment, discrimination, security breaches, hacked "
                    "accounts, threats or other matters needing a human.")
    summary: str = Field(
        description="One-line summary of what the employee wants NOW, with references "
                    "to earlier messages resolved.")


# ---------- Prompt ----------
ROUTER_PROMPT = f"""
You are the routing agent of an internal employee support desk. You do NOT answer
questions. You only decide which department(s) should handle the request.

## Departments
{departments_for_prompt()}

## Rules
1. Split the request into one task per department involved. A request can need
   1 to 4 departments. Never create two tasks for the same department.
2. Each sub_query must make sense on its own, because each department sees ONLY
   its sub_query, not the original message. Keep all details the employee gave.
3. Do not split a single issue across departments unless it truly needs both.
4. Disambiguation:
   - Account, login, password, VPN or email access problems -> it_admin
   - IT security rules, password rules, acceptable use of IT -> it_admin
   - Physical devices, Wi-Fi, printers, network hardware -> hardware
   - Salary, payslips, tax, reimbursements -> payroll (not hr)
   - Leave, policies, letters, workplace conduct -> hr
5. Greetings, vague messages ("it's not working") and anything unrelated to
   workplace support -> general. Use general ONLY if nothing else applies.
   Always return at least one task; a greeting is a general task.
6. Priority: critical = security breach or harassment; high = blocks work right now
   (can't log in, laptop dead, salary missing); medium = needs action soon;
   low = information questions and greetings.

## Conversation context
You may receive earlier messages for context. Route ONLY the latest message.
7. Use the conversation to resolve references like "yes", "that one", "same for
   my email", or answers to a question support asked. A reply to a department's
   question goes to THAT department.
8. Write the sub_query with every detail it needs from earlier messages (dates,
   leave types, amounts, systems), so it stands alone without the conversation.
   When the employee answers a list of requested fields, label each value with
   the field it answers (e.g. "category: travel, amount: 3000"), and keep their
   values exactly as given. Never drop or reinterpret a value they supplied.
9. Do not re-route earlier requests that were already answered. If the latest
   message changes topic, route only the new topic.

## Examples
- "My laptop won't turn on and I didn't get my salary" -> hardware ("My laptop won't
  turn on"), payroll ("My salary for this month hasn't been credited")
- "Can't log in to VPN" -> it_admin only
- "Wi-Fi keeps dropping on my floor" -> hardware only
- "I'm a new joiner and need a laptop and an email account" -> hardware + it_admin
- Support (HR) asked "Would you like to apply for earned leave for 10-11 November
  instead?" and the employee says "yes" -> hr ("Apply earned leave from 10 November
  to 11 November")
- Support (General) asked what isn't working and the employee says "my VPN"
  -> it_admin ("My VPN is not working")
- Support (Payroll) asked for category, amount, expense date and description, and
  the employee says "Meals, 400, 2026-10-20, team lunch" -> payroll ("Submit a
  reimbursement with category: meals, amount: 400, expense date: 2026-10-20,
  description: team lunch")
- Support (IT Admin) reset the VPN password and the employee says "same for my
  email" -> it_admin ("Reset my email password")
""".strip()


# ---------- Safety net ----------
MAX_TASKS = 4
SENSITIVE_PATTERN = re.compile(
    r"\b(harass\w*|discriminat\w*|bully\w*|hack\w*|phish\w*|breach\w*|"
    r"stolen|threat\w*|assault\w*|inappropriate)\b",
    re.IGNORECASE,
)
# Departments that own sensitive matters (harassment -> HR, security -> IT Admin)
SENSITIVE_OWNERS = (Department.HR, Department.IT_ADMIN)


def create_router(model_client: ChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="router_agent",
        model_client=model_client,
        system_message=ROUTER_PROMPT,
        output_content_type=RoutingDecision,
    )


def _fallback(query: str, reason: str, priority: Priority = Priority.MEDIUM) -> RoutingDecision:
    """Routes the whole query to General. Used when routing fails or returns nothing."""
    return RoutingDecision(
        tasks=[RoutedTask(department=Department.GENERAL, sub_query=query,
                          priority=priority, reason=reason)],
        is_sensitive=bool(SENSITIVE_PATTERN.search(query)),
        summary=query[:100],
    )


def _post_process(decision: RoutingDecision, query: str) -> RoutingDecision:
    """Deterministic clean-up so the orchestrator always gets a sane plan."""
    # 1. Merge duplicate departments
    merged: dict[Department, RoutedTask] = {}
    for task in decision.tasks:
        if task.department in merged:
            existing = merged[task.department]
            existing.sub_query += f" Also: {task.sub_query}"
            if PRIORITY_RANK[task.priority] > PRIORITY_RANK[existing.priority]:
                existing.priority = task.priority
        else:
            merged[task.department] = task.model_copy()

    # 2. Drop 'general' when a real department is involved
    if len(merged) > 1:
        merged.pop(Department.GENERAL, None)

    tasks = list(merged.values())
    if not tasks:
        # Usually a greeting the LLM decided needs no department
        return _fallback(query, "Router returned no tasks", Priority.LOW)

    # 3. Keyword safety net for sensitive matters the LLM might miss
    is_sensitive = decision.is_sensitive or bool(SENSITIVE_PATTERN.search(query))

    # 4. Sensitive matters are always critical for the departments that own them
    if is_sensitive:
        for task in tasks:
            if task.department in SENSITIVE_OWNERS:
                task.priority = Priority.CRITICAL

    # 5. Highest priority first, capped
    tasks.sort(key=lambda t: PRIORITY_RANK[t.priority], reverse=True)
    tasks = tasks[:MAX_TASKS]

    return decision.model_copy(update={"tasks": tasks, "is_sensitive": is_sensitive})


async def route_query(query: str, model_client: ChatCompletionClient,
                      history_text: str = "") -> RoutingDecision:
    """Classifies the latest message into department tasks, using recent conversation
    history (if any) to resolve references. Never raises: falls back to General."""
    if history_text:
        task = (f"## Conversation so far (context only)\n{history_text}\n\n"
                f"## Latest employee message (route THIS)\n{query}")
    else:
        task = query

    router = create_router(model_client)  # fresh agent per call; agents are stateful
    try:
        result = await router.run(task=task)
        message = result.messages[-1]
        if isinstance(message, StructuredMessage) and isinstance(message.content, RoutingDecision):
            return _post_process(message.content, query)
        logger.warning("Router returned unexpected message type: %s", type(message).__name__)
        return _fallback(query, "Unexpected router output")
    except Exception as exc:
        logger.exception("Routing failed: %s", exc)
        return _fallback(query, "Routing error")