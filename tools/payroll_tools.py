from datetime import date

from data.mock_db import CURRENCY, PAYSLIPS
from tools.common import employee_error


def get_payslip(employee_id: str, month: str) -> dict:
    """Get the payslip for a month in YYYY-MM format."""
    if err := employee_error(employee_id):
        return err
    for slip in PAYSLIPS[employee_id]:
        if slip["month"] == month:
            return {"currency": CURRENCY, **slip}
    return {"error": f"No payslip for {month}.",
            "available_months": [s["month"] for s in PAYSLIPS[employee_id]]}


def check_salary_status(employee_id: str) -> dict:
    """Check whether the most recent salary has been credited, and why not if held."""
    if err := employee_error(employee_id):
        return err
    slips = PAYSLIPS[employee_id]
    if not slips:
        return {"status": "no_payroll_yet",
                "message": "First salary is processed in the payroll cycle after joining."}
    return {"currency": CURRENCY, **slips[-1]}


def submit_reimbursement(employee_id: str, category: str, amount: float,
                         expense_date: str, description: str) -> dict:
    """Submit an expense claim. category: travel, internet or meals.
    expense_date in YYYY-MM-DD. A receipt must be uploaded separately."""
    if err := employee_error(employee_id):
        return err
    limits = {"travel": 5000, "internet": 1000, "meals": 500}
    if category not in limits:
        return {"error": f"Invalid category. Choose from {list(limits)}."}
    try:
        age = (date.today() - date.fromisoformat(expense_date)).days
    except ValueError:
        return {"error": "expense_date must be YYYY-MM-DD."}
    if age > 30:
        return {"error": "Claims must be filed within 30 days of the expense."}
    if amount > limits[category]:
        return {"error": f"Amount exceeds {category} limit of {limits[category]} {CURRENCY}."}
    return {"status": "submitted", "category": category, "amount": amount,
            "currency": CURRENCY, "next_step": "Upload the receipt in the expense portal."}