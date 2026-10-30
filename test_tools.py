from pprint import pprint

from tools import TOOLS_BY_DEPARTMENT
from tools.common import TICKETS
from tools.hr_tools import apply_leave, get_leave_balance
from tools.it_tools import report_security_incident, reset_password
from tools.payroll_tools import check_salary_status
from tools.hardware_tools import check_service_status, get_my_assets

print("== Leave ==")
pprint(get_leave_balance("E1001"))
pprint(apply_leave("E1002", "casual", "2026-11-10", "2026-11-11", "Family function"))  # should fail

print("\n== Payroll ==")
pprint(check_salary_status("E1001"))  # on_hold
pprint(check_salary_status("E1003"))  # new joiner

print("\n== IT ==")
pprint(reset_password("E1002", "vpn"))
pprint(report_security_incident("E1001", "Suspicious login from unknown location"))

print("\n== Hardware ==")
pprint(get_my_assets("E1002"))         # laptop out of warranty
pprint(check_service_status("wifi_floor_3"))

print("\n== Validation ==")
pprint(get_leave_balance("E9999"))     # unknown employee

print("\n== Tickets created ==")
pprint(TICKETS)

print("\n== Tool counts ==")
for dept, tools in TOOLS_BY_DEPARTMENT.items():
    print(f"{dept.value}: {[t.__name__ for t in tools]}")