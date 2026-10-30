from data.mock_db import ACCOUNTS
from tools.common import employee_error, escalate_to_human


def check_account_status(employee_id: str) -> dict:
    """Check status of the employee's email, VPN and SSO accounts."""
    if err := employee_error(employee_id):
        return err
    return {"employee_id": employee_id, "accounts": ACCOUNTS[employee_id]}


def reset_password(employee_id: str, system: str) -> dict:
    """Reset password and unlock an account. system: email, vpn or sso."""
    if err := employee_error(employee_id):
        return err
    accounts = ACCOUNTS[employee_id]
    if system not in accounts:
        return {"error": f"Unknown system. Choose from {list(accounts)}."}
    if accounts[system] == "not_created":
        return {"error": f"No {system} account exists yet. It must be provisioned first."}
    accounts[system] = "active"
    return {"status": "reset_link_sent", "system": system,
            "message": "Reset link sent to registered mobile. Valid for 15 minutes."}


def provision_account(employee_id: str, system: str) -> dict:
    """Create a new account (email, vpn or sso), e.g. for new joiners."""
    if err := employee_error(employee_id):
        return err
    accounts = ACCOUNTS[employee_id]
    if accounts.get(system) != "not_created":
        return {"error": f"{system} account already exists (status: {accounts.get(system)})."}
    accounts[system] = "active"
    return {"status": "provisioned", "system": system}


def request_software(employee_id: str, software_name: str, justification: str) -> dict:
    """Request installation or a license for software. Needs manager approval."""
    if err := employee_error(employee_id):
        return err
    return {"status": "pending_manager_approval", "software": software_name}


def report_security_incident(employee_id: str, description: str) -> dict:
    """Report a security incident such as a hacked account or phishing.
    Locks accounts and escalates to the security team immediately."""
    if err := employee_error(employee_id):
        return err
    for system in ACCOUNTS[employee_id]:
        if ACCOUNTS[employee_id][system] == "active":
            ACCOUNTS[employee_id][system] = "locked"
    result = escalate_to_human(employee_id, f"SECURITY INCIDENT: {description}")
    return {"accounts_locked": True, **result}