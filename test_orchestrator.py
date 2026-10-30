import asyncio
import sys

from orchestrator import handle_query

SCENARIOS = [
    ("E1002", "My VPN is locked and I want to take casual leave on 10th and 11th November"),
    ("E1001", "My October salary hasn't come and the Wi-Fi on my floor keeps dropping"),
    ("E1003", "I'm new here. I need my email account, a laptop and my offer letter"),
    ("E1001", "I think someone hacked my email, I got a weird login alert"),
    ("E1002", "My manager keeps making inappropriate comments about me"),
    ("E1001", "Hi! How many sick leaves do I have?"),
    ("E1002", "The Wi-Fi on my floor keeps dropping"),
]


def print_response(resp) -> None:
    r = resp.routing
    print(f"\nRouting: {r.summary} | sensitive={r.is_sensitive}")
    for res in resp.results:
        print(f"\n  [{res.status:7}] {res.task.department.value} "
              f"({res.task.priority.value}, {res.duration_s:.1f}s)")
        print(f"    sub-query: {res.task.sub_query}")
        for tc in res.tool_calls:
            flag = " ERROR" if tc.is_error else ""
            print(f"    tool: {tc.name}({tc.arguments}){flag}")

    print("\n" + "-" * 70 + "\nFINAL ANSWER:\n" + resp.final_answer + "\n" + "-" * 70)

    if resp.tickets:
        print("Tickets: " + ", ".join(f"{t['ticket_id']} ({t['department']}, {t['priority']})"
                                      for t in resp.tickets))
    print(f"Escalated: {resp.escalated}")
    tm = resp.timings
    print(f"Timings: routing {tm['routing']:.1f}s | specialists {tm['specialists']:.1f}s | "
          f"aggregation {tm['aggregation']:.1f}s | total {tm['total']:.1f}s | "
          f"parallel speedup {resp.parallel_speedup:.1f}x")


async def main() -> None:
    # python test_orchestrator.py 1   -> runs only scenario #1
    selected = [SCENARIOS[int(sys.argv[1])]] if len(sys.argv) > 1 else SCENARIOS
    for employee_id, query in selected:
        print(f"\n{'=' * 70}\n{employee_id}: {query}\n{'=' * 70}")
        print_response(await handle_query(query, employee_id))


asyncio.run(main())