from datetime import date

from data.mock_db import LEAVE_BALANCES, POLICIES
from tools.common import employee_error


def get_leave_balance(employee_id: str) -> dict:
    """Get remaining leave days by type (casual, sick, earned)."""
    if err := employee_error(employee_id):
        return err
    return {"employee_id": employee_id, "balance": LEAVE_BALANCES[employee_id]}


def apply_leave(employee_id: str, leave_type: str, start_date: str,
                end_date: str, reason: str) -> dict:
    """Apply for leave. leave_type: casual, sick or earned. Dates in YYYY-MM-DD format."""
    if err := employee_error(employee_id):
        return err
    balance = LEAVE_BALANCES[employee_id]
    if leave_type not in balance:
        return {"error": f"Invalid leave type. Choose from {list(balance)}."}
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError:
        return {"error": "Dates must be in YYYY-MM-DD format."}
    days = (end - start).days + 1
    if days <= 0:
        return {"error": "End date must be on or after start date."}
    if days > balance[leave_type]:
        return {"error": f"Insufficient {leave_type} leave: requested {days}, "
                         f"available {balance[leave_type]}."}
    balance[leave_type] -= days
    return {"status": "submitted_for_manager_approval", "leave_type": leave_type,
            "days": days, "remaining": balance[leave_type]}


def get_policy(topic: str) -> dict:
    """Look up a company policy. topic: leave, wfh, reimbursement, travel,
    it_security or code_of_conduct."""
    policy = POLICIES.get(topic.lower())
    if not policy:
        return {"error": f"No policy found for '{topic}'.", "available": list(POLICIES)}
    return {"topic": topic, "policy": policy}


def request_document(employee_id: str, document_type: str) -> dict:
    """Request an HR document: offer_letter, experience_letter,
    employment_verification or address_proof."""
    if err := employee_error(employee_id):
        return err
    allowed = {"offer_letter", "experience_letter", "employment_verification", "address_proof"}
    if document_type not in allowed:
        return {"error": f"Unknown document type. Choose from {sorted(allowed)}."}
    return {"status": "requested", "document_type": document_type,
            "delivery": "Emailed within 2 working days."}