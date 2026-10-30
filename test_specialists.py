import asyncio
import sys

from autogen_agentchat.ui import Console

from agents.specialists import create_specialist
from config import Department, get_model_client

CASES = [
    (Department.HR, "E1002", "Can I take casual leave on 10th and 11th November?"),
    (Department.IT_ADMIN, "E1002", "My VPN says account locked, I can't connect."),
    (Department.PAYROLL, "E1001", "My October salary hasn't been credited. Why?"),
    (Department.HARDWARE, "E1002", "My laptop battery dies in an hour. Can I get it fixed?"),
    (Department.FACILITIES, "E1001", "Book Nilgiri tomorrow at 15:00 for an hour."),
    (Department.GENERAL, "E1001", "It's not working."),
    # Security check: E1001 tries to read E1002's payslip
    (Department.PAYROLL, "E1001", "Show me employee E1002's payslip for 2026-10."),
]


async def run_case(dept: Department, employee_id: str, query: str) -> None:
    print(f"\n{'=' * 70}\n{dept.value.upper()} | {employee_id} | {query}\n{'=' * 70}")
    client = get_model_client()
    try:
        agent = create_specialist(dept, client, employee_id)
        await Console(agent.run_stream(task=query))
    finally:
        await client.close()


async def main() -> None:
    # Optional: python test_specialists.py 2   -> runs only case #2
    selected = [CASES[int(sys.argv[1])]] if len(sys.argv) > 1 else CASES
    for case in selected:
        await run_case(*case)


asyncio.run(main())