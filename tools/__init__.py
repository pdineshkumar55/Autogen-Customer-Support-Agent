from config import Department
from tools.common import escalate_to_human, get_employee_profile, make_create_ticket
from tools.hr_tools import apply_leave, get_leave_balance, get_policy, request_document
from tools.it_tools import (check_account_status, provision_account, report_security_incident,
                            request_software, reset_password)
from tools.payroll_tools import check_salary_status, get_payslip, submit_reimbursement
from tools.hardware_tools import (check_my_floor_services, check_service_status,
                                  get_my_assets, request_device)
from tools.facilities_tools import book_meeting_room, request_access_card

# Read-only knowledge every agent can use, so answers don't depend on perfect routing
SHARED_TOOLS = [get_policy, get_employee_profile]

# Department-specific actions
DEPARTMENT_TOOLS = {
    Department.HR: [get_leave_balance, apply_leave, request_document,
                    escalate_to_human, make_create_ticket("hr")],
    Department.IT_ADMIN: [check_account_status, reset_password, provision_account,
                          request_software, report_security_incident,
                          make_create_ticket("it_admin")],
    Department.PAYROLL: [get_payslip, check_salary_status, submit_reimbursement,
                         make_create_ticket("payroll")],
    Department.HARDWARE: [get_my_assets, check_my_floor_services, check_service_status,
                          request_device, make_create_ticket("hardware")],
    Department.FACILITIES: [book_meeting_room, request_access_card,
                            make_create_ticket("facilities")],
    Department.GENERAL: [escalate_to_human],
}

TOOLS_BY_DEPARTMENT = {
    dept: tools + SHARED_TOOLS for dept, tools in DEPARTMENT_TOOLS.items()
}