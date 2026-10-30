"""In-memory mock database. Replace with a real DB/API later."""

EMPLOYEES = {
    "E1001": {"name": "Priya Sharma", "team": "Engineering", "manager": "Rahul Mehta",
              "email": "priya.sharma@example.com", "join_date": "2022-03-14", "floor": 3},
    "E1002": {"name": "Arjun Nair", "team": "Sales", "manager": "Kavya Rao",
              "email": "arjun.nair@example.com", "join_date": "2019-07-01", "floor": 2},
    "E1003": {"name": "Meena Iyer", "team": "Finance", "manager": "Suresh Babu",
              "email": "meena.iyer@example.com", "join_date": "2026-11-02", "floor": 1},
}

LEAVE_BALANCES = {
    "E1001": {"casual": 4, "sick": 6, "earned": 12},
    "E1002": {"casual": 0, "sick": 2, "earned": 20},
    "E1003": {"casual": 1, "sick": 1, "earned": 0},
}

PAYSLIPS = {
    "E1001": [
        {"month": "2026-09", "gross": 120000, "net": 98500, "status": "credited", "credited_on": "2026-09-30"},
        {"month": "2026-10", "gross": 120000, "net": 98500, "status": "on_hold",
         "reason": "Bank account verification failed after bank detail change"},
    ],
    "E1002": [
        {"month": "2026-09", "gross": 90000, "net": 76200, "status": "credited", "credited_on": "2026-09-30"},
        {"month": "2026-10", "gross": 90000, "net": 76200, "status": "credited", "credited_on": "2026-10-30"},
    ],
    "E1003": [],  # new joiner, no payslips yet
}
CURRENCY = "INR"

ACCOUNTS = {
    "E1001": {"email": "active", "vpn": "active", "sso": "active"},
    "E1002": {"email": "active", "vpn": "locked", "sso": "active"},
    "E1003": {"email": "not_created", "vpn": "not_created", "sso": "not_created"},
}

ASSETS = {
    "E1001": [{"asset_id": "LAP-2231", "type": "laptop", "model": "Dell Latitude 5440",
               "warranty_until": "2027-05-01"}],
    "E1002": [{"asset_id": "LAP-1187", "type": "laptop", "model": "Lenovo ThinkPad T14",
               "warranty_until": "2025-12-31"},
              {"asset_id": "MON-0442", "type": "monitor", "model": "Dell P2422H",
               "warranty_until": "2027-01-15"}],
    "E1003": [],
}

SERVICE_STATUS = {
    "email": "operational",
    "vpn": "operational",
    "wifi_floor_1": "operational",
    "wifi_floor_2": "operational",
    "wifi_floor_3": "degraded - engineers investigating, ETA 2 hours",
    "printer_floor_2": "offline - toner replacement scheduled today",
}

MEETING_ROOMS = {"Everest": 10, "Nilgiri": 6, "Kanchenjunga": 4}
ROOM_BOOKINGS: list[dict] = []

POLICIES = {
    "leave": "Casual: 12/yr, Sick: 10/yr, Earned: 18/yr (carry forward max 30). "
             "Apply at least 3 working days in advance for planned leave.",
    "wfh": "Up to 2 WFH days per week with manager approval.",
    "reimbursement": "Claims must be filed within 30 days of expense with a receipt. "
                     "Limits: travel 5000/trip, internet 1000/month, meals 500/day.",
    "travel": "Domestic travel needs manager approval; international needs director approval. "
              "Book through the travel desk at least 7 days ahead.",
    "it_security": "Never share passwords. Report suspected phishing or account compromise "
                   "immediately. Passwords rotate every 90 days.",
    "code_of_conduct": "Harassment of any kind is not tolerated. Complaints are handled "
                       "confidentially by the HR grievance committee.",
}