from datetime import date

from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient

from agents.prompts import BASE_RULES, DEPARTMENT_PROMPTS
from agents.tool_binding import bind_employee
from config import DEPARTMENTS, Department
from tools import TOOLS_BY_DEPARTMENT


def create_specialist(
    department: Department,
    model_client: ChatCompletionClient,
    employee_id: str,
) -> AssistantAgent:
    """Creates a fresh specialist agent for one department and one employee."""
    info = DEPARTMENTS[department]
    system_message = (
        DEPARTMENT_PROMPTS[department].strip()
        + "\n\n"
        + BASE_RULES.format(label=info.label, today=date.today().isoformat())
    )
    tools = [bind_employee(tool, employee_id) for tool in TOOLS_BY_DEPARTMENT[department]]

    return AssistantAgent(
        name=f"{department.value}_agent",
        model_client=model_client,
        tools=tools,
        system_message=system_message,
        description=info.scope,
        reflect_on_tool_use=True,   # turn raw tool results into a natural reply
        max_tool_iterations=5,      # allow chains like check status -> reset
    )