import os
import warnings
from dataclasses import dataclass
from enum import Enum
import warnings

from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()

# Harmless OpenAI SDK / AutoGen logging mismatch on structured outputs
warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)

# ---------- Settings ----------
class Settings:
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "60"))


def validate_settings() -> None:
    if not Settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your .env file.")


# ---------- Department registry ----------
class Department(str, Enum):
    HR = "hr"
    IT_ADMIN = "it_admin"
    PAYROLL = "payroll"
    HARDWARE = "hardware"
    FACILITIES = "facilities"
    GENERAL = "general"


@dataclass(frozen=True)
class DepartmentInfo:
    label: str
    icon: str
    scope: str  # used in the router prompt to decide where a query goes


DEPARTMENTS: dict[Department, DepartmentInfo] = {
    Department.HR: DepartmentInfo(
        "HR", "🧑‍💼",
        "Leave balance and requests, company policies, onboarding/offboarding, "
        "offer/experience letters, benefits, grievances and workplace complaints."),
    Department.IT_ADMIN: DepartmentInfo(
        "IT Admin", "🔐",
        "User accounts, password resets, VPN, email setup, software installation "
        "and licenses, access permissions, security incidents like hacked accounts."),
    Department.PAYROLL: DepartmentInfo(
        "Payroll & Accounts", "💰",
        "Salary credit, payslips, tax deductions and forms, reimbursements, "
        "expense claims, bank detail changes, bonuses."),
    Department.HARDWARE: DepartmentInfo(
        "Hardware & Technical", "💻",
        "Laptop/desktop faults, new device requests, printers, monitors, "
        "peripherals, Wi-Fi and network connectivity issues."),
    Department.FACILITIES: DepartmentInfo(
        "Facilities", "🏢",
        "Desk/seat allocation, ID/access cards, meeting rooms, cafeteria, "
        "office maintenance, business travel and transport."),
    Department.GENERAL: DepartmentInfo(
        "General", "💬",
        "Greetings, unclear or ambiguous requests needing clarification, "
        "and anything outside the other departments."),
}


def departments_for_prompt() -> str:
    """Formats the registry as text for the router's system prompt."""
    return "\n".join(
        f"- {dept.value}: {info.scope}" for dept, info in DEPARTMENTS.items()
    )


# ---------- Model client factory ----------
def get_model_client(temperature: float | None = None) -> OpenAIChatCompletionClient:
    """Creates a NEW client. Create one per request and close it when done."""
    validate_settings()
    return OpenAIChatCompletionClient(
        model=Settings.MODEL_NAME,
        api_key=Settings.OPENAI_API_KEY,
        temperature=Settings.TEMPERATURE if temperature is None else temperature,
    )


if __name__ == "__main__":
    validate_settings()
    print(f"Model: {Settings.MODEL_NAME}, temperature: {Settings.TEMPERATURE}")
    print("Departments:\n" + departments_for_prompt())