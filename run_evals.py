import argparse
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from config import Settings, get_model_client
from evals.checks import judge, reset_state, run_checks
from evals.scenarios import SCENARIOS, Scenario
from memory import Turn
from orchestrator import handle_query
from usage import Usage, fmt_cost, usage_from_client


async def run_one(s: Scenario, judge_client) -> dict:
    reset_state()   # once per scenario; setup turns intentionally share state
    record = {"id": s.id, "employee_id": s.employee_id, "query": s.query,
              "setup": s.setup, "failures": [], "warnings": [], "answer": "", "total_s": 0.0,
              "tokens": 0, "cost_usd": None, "run_tokens": 0, "run_cost_usd": None}
    history: list[Turn] = []
    run_usage = Usage()   # everything this scenario spent, setup turns included
    try:
        for setup_query in s.setup:
            setup_resp = await handle_query(setup_query, s.employee_id, history=history)
            history += setup_resp.as_turns()
            run_usage = run_usage + setup_resp.total_usage
        resp = await handle_query(s.query, s.employee_id, history=history)
        run_usage = run_usage + resp.total_usage
    except Exception as exc:
        record["failures"].append(f"crashed: {exc!r}")
        record["passed"] = False
        return record

    checks = run_checks(s, resp)
    record["failures"] += checks.failures
    record["warnings"] += checks.warnings

    if judge_client and s.judge:
        try:
            verdict = await judge(s, resp, judge_client)
            if not verdict.passed:
                record["failures"].append(f"judge: {verdict.reason}")
        except Exception as exc:
            record["warnings"].append(f"judge error: {exc!r}")

    record.update(
        passed=not record["failures"],
        answer=resp.final_answer,
        total_s=round(resp.timings["total"], 1),
        departments=sorted(r.task.department.value for r in resp.results),
        tools={r.task.department.value: [tc.name for tc in r.tool_calls] for r in resp.results},
        tickets=[f"{t['ticket_id']} ({t['department']})" for t in resp.tickets],
        escalated=resp.escalated,
        sub_queries={r.task.department.value: r.task.sub_query for r in resp.results},
        tokens=resp.total_usage.total_tokens,          # the final answer only
        llm_calls=resp.total_usage.calls,
        cost_usd=resp.cost_usd,
        run_tokens=run_usage.total_tokens,             # including setup turns
        run_cost_usd=run_usage.cost_usd(Settings.MODEL_NAME),
    )
    return record


def print_record(r: dict, verbose: bool) -> None:
    status = "PASS" if r["passed"] else "FAIL"
    print(f"{status}  {r['id']:32} {r['total_s']:5.1f}s {r['tokens']:>7,} tok "
          f"{fmt_cost(r['cost_usd']):>9}  {', '.join(r.get('departments', []))}")
    for f in r["failures"]:
        print(f"      FAIL: {f}")
    for w in r["warnings"]:
        print(f"      WARN: {w}")
    if verbose or not r["passed"]:
        print(f"      sub-queries: {r.get('sub_queries')}")
        print(f"      tools: {r.get('tools')}")
        print(f"      tickets: {r.get('tickets')}")
        answer = r["answer"].replace("\n", "\n         ")
        print(f"      answer:\n         {answer}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run support desk regression scenarios.")
    parser.add_argument("--only", help="Comma-separated scenario ids to run")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per scenario (flakiness check)")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge checks")
    parser.add_argument("--verbose", action="store_true", help="Print every answer")
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        scenarios = [s for s in SCENARIOS if s.id in wanted]
        if unknown := wanted - {s.id for s in scenarios}:
            print(f"Unknown scenario ids: {sorted(unknown)}")
            return 2

    judge_client = None if args.no_judge else get_model_client(temperature=0)
    judge_usage = Usage()
    records = []
    try:
        for s in scenarios:   # sequential: scenarios share and reset mock state
            for run in range(1, args.repeat + 1):
                record = await run_one(s, judge_client)
                record["run"] = run
                print_record(record, args.verbose)
                records.append(record)
        if judge_client:
            judge_usage = usage_from_client(judge_client, calls=0)
    finally:
        if judge_client:
            await judge_client.close()

    # ---------- Summary ----------
    by_id = defaultdict(list)
    for r in records:
        by_id[r["id"]].append(r["passed"])
    print("\n" + "=" * 60 + "\nSUMMARY")
    for sid, results in by_id.items():
        passed = sum(results)
        note = "" if passed == len(results) else ("  <- flaky" if passed else "  <- failing")
        print(f"  {sid:32} {passed}/{len(results)}{note}")
    total_passed = sum(r["passed"] for r in records)
    print(f"\n{total_passed}/{len(records)} runs passed")

    # ---------- Cost ----------
    model = Settings.MODEL_NAME
    agent_tokens = sum(r["run_tokens"] for r in records)
    agent_costs = [r["run_cost_usd"] for r in records if r["run_cost_usd"] is not None]
    answer_costs = [r["cost_usd"] for r in records if r["cost_usd"] is not None]
    judge_cost = judge_usage.cost_usd(model)
    print(f"\nCOST ({model})")
    print(f"  System under test: {agent_tokens:,} tokens, {fmt_cost(sum(agent_costs) if agent_costs else None)}")
    if judge_client:
        print(f"  LLM judge:         {judge_usage.total_tokens:,} tokens, {fmt_cost(judge_cost)}")
    if answer_costs:
        avg = sum(answer_costs) / len(answer_costs)
        print(f"  Average per answer: {fmt_cost(avg)}  (about ${avg * 1000:.2f} per 1,000 answers)")
        most = max(records, key=lambda r: r["cost_usd"] or 0)
        print(f"  Most expensive:    {most['id']} at {fmt_cost(most['cost_usd'])}, {most['tokens']:,} tokens")

    # ---------- Report ----------
    Path("reports").mkdir(exist_ok=True)
    path = Path("reports") / f"eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    report = {
        "model": model,
        "passed": total_passed,
        "runs": len(records),
        "agent_tokens": agent_tokens,
        "agent_cost_usd": sum(agent_costs) if agent_costs else None,
        "judge_tokens": judge_usage.total_tokens,
        "judge_cost_usd": judge_cost,
        "records": records,
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report saved: {path}")

    return 0 if total_passed == len(records) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))