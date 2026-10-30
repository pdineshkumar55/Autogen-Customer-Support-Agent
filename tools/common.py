import itertools
import threading
from datetime import datetime
from typing import Callable

from data.mock_db import EMPLOYEES

TICKETS: list[dict] = []
_lock = threading.Lock()
_counter = itertools.count(1001)


def employee_error(employee_id: str) -> dict | None:
    """Returns an error dict if the employee doesn't exist, else None."""
    if employee_id not in EMPLOYEES:
        return {"error": f"Employee '{employee_id}' not found."}
    return None


def _save_ticket(department: str, employee_id: str, summary: str, priority: str) -> dict:
    with _lock:
        ticket = {
            "ticket_id": f"TKT-{next(_counter)}",
            "department": department,
            "employee_id": employee_id,
            "summary": summary,
            "priority": priority,
            "status": "open",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        TICKETS.append(ticket)
    return ticket


def make_create_ticket(department: str) -> Callable:
    """Builds a create_ticket tool bound to one department."""
    def create_ticket(employee_id: str, summary: str, priority: str = "medium") -> dict:
        """Create a support ticket when the issue can't be resolved immediately.
        priority must be one of: low, medium, high, critical."""
        if err := employee_error(employee_id):
            return err
        if priority not in {"low", "medium", "high", "critical"}:
            priority = "medium"
        return _save_ticket(department, employee_id, summary, priority)
    return create_ticket


def escalate_to_human(employee_id: str, reason: str) -> dict:
    """Escalate to a human support specialist. Use for sensitive matters (harassment,
    security breaches, legal issues) or when the user explicitly asks for a person."""
    ticket = _save_ticket("human_escalation", employee_id, reason, "critical")
    return {"escalated": True, "ticket_id": ticket["ticket_id"],
            "message": "A human specialist will contact the employee within 1 business hour."}


def get_employee_profile(employee_id: str) -> dict:
    """Get the employee's basic profile: name, team, manager, email, join date, floor."""
    if err := employee_error(employee_id):
        return err
    return {"employee_id": employee_id, **EMPLOYEES[employee_id]}