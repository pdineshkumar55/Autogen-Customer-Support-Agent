from datetime import date

from data.mock_db import ASSETS, EMPLOYEES, SERVICE_STATUS
from tools.common import employee_error


def get_my_assets(employee_id: str) -> dict:
    """List devices assigned to the employee, with warranty status."""
    if err := employee_error(employee_id):
        return err
    today = date.today()
    assets = [
        {**a, "under_warranty": date.fromisoformat(a["warranty_until"]) >= today}
        for a in ASSETS[employee_id]
    ]
    return {"employee_id": employee_id, "assets": assets}


def check_my_floor_services(employee_id: str, service_type: str) -> dict:
    """Check the status of Wi-Fi or the printer on the employee's OWN floor.
    service_type: 'wifi' or 'printer'. Always use this for 'my Wi-Fi', 'my floor',
    'the printer near me' or similar problems. Follow the next_step it returns."""
    if err := employee_error(employee_id):
        return err
    service_type = service_type.lower().replace("-", "").replace(" ", "")
    if service_type not in {"wifi", "printer"}:
        return {"error": "service_type must be 'wifi' or 'printer'."}

    floor = EMPLOYEES[employee_id]["floor"]
    status = SERVICE_STATUS.get(f"{service_type}_floor_{floor}")

    if status is not None and status != "operational":
        next_step = ("Known outage on this floor: share the status and ETA. "
                     "Do NOT create a ticket.")
    else:
        status = status or "no outage recorded"
        next_step = ("ACTION REQUIRED: there is no known outage, so the problem is local "
                     "to this employee. In THIS reply, suggest 1-2 quick checks AND call "
                     "create_ticket, then share the ticket ID.")
    return {"floor": floor, "service": service_type, "status": status, "next_step": next_step}

def check_service_status(service: str) -> dict:
    """Check company-wide services for known outages, e.g. 'email' or 'vpn'.
    For the employee's own floor, use check_my_floor_services instead.
    Use 'all' to list every service."""
    if service == "all":
        return SERVICE_STATUS
    status = SERVICE_STATUS.get(service)
    if status is None:
        return {"error": f"Unknown service '{service}'.", "known": list(SERVICE_STATUS)}
    return {"service": service, "status": status}


def request_device(employee_id: str, device_type: str, reason: str) -> dict:
    """Request a new or replacement device: laptop, monitor, keyboard, mouse or headset."""
    if err := employee_error(employee_id):
        return err
    eta = {"laptop": "3-5 working days"}.get(device_type, "1-2 working days")
    return {"status": "requested", "device_type": device_type, "eta": eta}