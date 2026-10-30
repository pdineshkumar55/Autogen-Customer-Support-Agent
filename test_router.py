import asyncio
import time

from agents.router import Priority, route_query
from config import Department as D, get_model_client

# (query, expected departments, expected sensitive flag)
SCENARIOS = [
    ("How many leave days do I have left?", {D.HR}, False),
    ("My laptop won't boot and my salary wasn't credited this month", {D.HARDWARE, D.PAYROLL}, False),
    ("I'm joining next week, need a laptop, email account and my offer letter",
     {D.HARDWARE, D.IT_ADMIN, D.HR}, False),
    ("Reset my VPN password", {D.IT_ADMIN}, False),
    ("It's not working", {D.GENERAL}, False),
    ("I think my email account was hacked", {D.IT_ADMIN}, True),
    ("My manager keeps making inappropriate comments about me", {D.HR}, True),
    ("What's the weather tomorrow?", {D.GENERAL}, False),
    ("I want to raise a reimbursement", {D.PAYROLL}, False),
    ("Wi-Fi on floor 3 is down and I need a room for a client call at 4pm",
     {D.HARDWARE, D.FACILITIES}, False),
    ("Hi there!", {D.GENERAL}, False),
    ("Lost my ID card and my laptop on the train", {D.FACILITIES, D.HARDWARE}, False),
]


def check(decision, expected: set, exp_sensitive: bool) -> list[str]:
    """Returns a list of failure reasons (empty list = pass)."""
    problems = []
    got = {t.department for t in decision.tasks}
    if got != expected:
        problems.append(f"departments: expected {sorted(d.value for d in expected)}, "
                        f"got {sorted(d.value for d in got)}")
    if decision.is_sensitive != exp_sensitive:
        problems.append(f"sensitive: expected {exp_sensitive}, got {decision.is_sensitive}")
    if exp_sensitive and not any(t.priority == Priority.CRITICAL for t in decision.tasks):
        problems.append("sensitive request has no critical task")
    return problems


async def main() -> None:
    client = get_model_client(temperature=0)  # classification should be deterministic
    try:
        start = time.perf_counter()
        decisions = await asyncio.gather(*(route_query(q, client) for q, _, _ in SCENARIOS))
        elapsed = time.perf_counter() - start
    finally:
        await client.close()

    passed = 0
    for (query, expected, exp_sensitive), decision in zip(SCENARIOS, decisions):
        problems = check(decision, expected, exp_sensitive)
        passed += not problems
        print(f"\n{'PASS' if not problems else 'FAIL'} | {query}")
        for problem in problems:
            print(f"   !! {problem}")
        print(f"   sensitive={decision.is_sensitive} | {decision.summary}")
        for t in decision.tasks:
            print(f"   -> [{t.priority.value:8}] {t.department.value:10} | {t.sub_query}")

    print(f"\n{passed}/{len(SCENARIOS)} passed in {elapsed:.1f}s (all routed in parallel)")


asyncio.run(main())