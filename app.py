import asyncio

import streamlit as st

from config import DEPARTMENTS, Settings, validate_settings
from data.mock_db import EMPLOYEES
from data.state import reset_state
from memory import Turn
from orchestrator import SupportResponse, handle_query
from tools.common import TICKETS
from usage import PRICING_PER_1M, Usage, fmt_cost

st.set_page_config(page_title="Employee Support Desk", page_icon="🛟", layout="wide")

SAMPLES = [
    ("📅 Leave balance", "How many leave days do I have left?"),
    ("🔐 VPN + leave", "My VPN is locked and I want to take casual leave on 10th and 11th November"),
    ("💰 Salary + Wi-Fi", "My October salary hasn't come and the Wi-Fi on my floor keeps dropping"),
    ("🧑‍💻 New joiner", "I'm new here. I need my email account, a laptop and my offer letter"),
    ("🚨 Hacked account", "I think someone hacked my email, I got a weird login alert"),
    ("🏢 Book a room", "Book Nilgiri tomorrow at 15:00 for an hour"),
]
STATUS_ICON = {"success": "✅", "timeout": "⏱️", "error": "❌"}
PRIORITY_COLOR = {"low": "gray", "medium": "blue", "high": "orange", "critical": "red"}


# ---------- Setup ----------
try:
    validate_settings()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []


def clear_chat() -> None:
    st.session_state.messages = []


# ---------- Rendering helpers ----------
def render_usage(resp: SupportResponse) -> None:
    total = resp.total_usage
    cost = resp.cost_usd
    cols = st.columns(4)
    cols[0].metric("Tokens", f"{total.total_tokens:,}")
    cols[1].metric("LLM calls", total.calls)
    cols[2].metric("Cost of this answer", fmt_cost(cost))
    cols[3].metric("Per 1,000 answers", "n/a" if cost is None else f"${cost * 1000:.2f}")

    rows = [{
        "Stage": stage.title(),
        "LLM calls": u.calls,
        "Input tokens": u.prompt_tokens,
        "Output tokens": u.completion_tokens,
        "Cost (USD)": fmt_cost(u.cost_usd(resp.model)),
    } for stage, u in resp.usage.items()]
    st.dataframe(rows, hide_index=True)

    if cost is None:
        st.caption(f"No price configured for '{resp.model}'. Add it to PRICING_PER_1M in usage.py.")
    else:
        st.caption("Estimate at list prices; cached input tokens are counted at full price.")


def render_details(resp: SupportResponse) -> None:
    routing = resp.routing
    with st.expander("🔍 Behind the scenes"):
        cols = st.columns(4)
        cols[0].metric("Total time", f"{resp.timings['total']:.1f}s")
        cols[1].metric("Routing", f"{resp.timings['routing']:.1f}s")
        cols[2].metric("Agents (parallel)", f"{resp.timings['specialists']:.1f}s")
        cols[3].metric("Parallel speedup", f"{resp.parallel_speedup:.1f}x")
        render_usage(resp)

        sensitive = "  ·  :red[**sensitive**]" if routing.is_sensitive else ""
        st.markdown(f"**Detected intent:** {routing.summary}{sensitive}")
        if resp.used_history:
            st.caption("💬 Interpreted using the earlier conversation")

        for res in resp.results:
            info = DEPARTMENTS[res.task.department]
            priority = res.task.priority.value
            with st.container(border=True):
                st.markdown(
                    f"{info.icon} **{info.label}** {STATUS_ICON.get(res.status, '')} · "
                    f":{PRIORITY_COLOR[priority]}[{priority}] · {res.duration_s:.1f}s"
                )
                retried = " · 🔁 retried" if res.retried else ""
                st.caption(f"{res.usage.calls} LLM calls · {res.usage.total_tokens:,} tokens · "
                           f"{fmt_cost(res.usage.cost_usd(resp.model))}{retried}")
                st.caption(f"Sub-query: {res.task.sub_query}")
                for tc in res.tool_calls:
                    warning = " ⚠️ error" if tc.is_error else ""
                    st.markdown(f"🔧 `{tc.name}({tc.arguments})`{warning}")
                    st.code(tc.result, language="python")
                if not res.tool_calls:
                    st.caption("No tools called.")
                st.markdown("**Agent answer:**")
                st.markdown(res.response)


def render_assistant(message: dict) -> None:
    st.markdown(message["content"])
    resp: SupportResponse | None = message.get("response")
    if resp is None:
        return
    if resp.escalated:
        st.warning("🚨 Escalated to a human specialist.")
    footer = [f"{resp.timings['total']:.1f}s", f"{resp.total_usage.total_tokens:,} tokens",
              fmt_cost(resp.cost_usd)]
    if resp.tickets:
        footer.append("Tickets: " + ", ".join(t["ticket_id"] for t in resp.tickets))
    st.caption(" · ".join(footer))
    render_details(resp)


# ---------- Sidebar ----------
with st.sidebar:
    st.title("🛟 Support Desk")
    st.selectbox(
        "Signed in as",
        options=list(EMPLOYEES),
        format_func=lambda e: f"{EMPLOYEES[e]['name']} ({e})",
        key="employee_id",
        on_change=clear_chat,   # new identity = new conversation
    )
    employee = EMPLOYEES[st.session_state.employee_id]
    st.caption(f"{employee['team']} · Floor {employee['floor']} · Manager: {employee['manager']}")

    st.divider()
    st.subheader("Try a scenario")
    for label, query in SAMPLES:
        if st.button(label, key=f"sample_{label}"):
            st.session_state.pending = query

    # Session usage
    responses = [m["response"] for m in st.session_state.messages if m.get("response")]
    if responses:
        st.divider()
        st.subheader("This session")
        session_usage = sum((r.total_usage for r in responses), Usage())
        costs = [r.cost_usd for r in responses]
        session_cost = None if any(c is None for c in costs) else sum(costs)
        col1, col2 = st.columns(2)
        col1.metric("Tokens", f"{session_usage.total_tokens:,}")
        col2.metric("Cost", fmt_cost(session_cost))
        st.caption(f"{len(responses)} answers · {session_usage.calls} LLM calls")

    st.divider()
    st.subheader("My tickets")
    my_tickets = [t for t in TICKETS if t["employee_id"] == st.session_state.employee_id]
    if not my_tickets:
        st.caption("No tickets yet.")
    for t in reversed(my_tickets):
        color = PRIORITY_COLOR.get(t["priority"], "gray")
        st.markdown(f"**{t['ticket_id']}** · {t['department']} · :{color}[{t['priority']}]  \n"
                    f"<small>{t['summary'][:90]}</small>", unsafe_allow_html=True)

    st.divider()
    col1, col2 = st.columns(2)
    if col1.button("Clear chat"):
        clear_chat()
        st.rerun()
    if col2.button("Reset data", help="Restore all mock data and delete tickets"):
        reset_state()
        clear_chat()
        st.rerun()
    price = PRICING_PER_1M.get(Settings.MODEL_NAME)
    price_text = f" · ${price[0]}/${price[1]} per 1M tokens" if price else " · no price set"
    st.caption(f"Model: {Settings.MODEL_NAME}{price_text}")


# ---------- Main chat ----------
st.title("Employee Support Desk")
st.caption("Ask anything about HR, IT accounts, payroll, hardware or facilities. "
           "Your request is routed to specialist agents that work in parallel.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            render_assistant(message)
        else:
            st.markdown(message["content"])

typed = st.chat_input("Describe your issue...")
pending = st.session_state.get("pending")
if pending:
    del st.session_state["pending"]
prompt = typed or pending

if prompt:
    # Build history from the chat BEFORE adding the new message
    history: list[Turn] = []
    for message in st.session_state.messages:
        if message["role"] == "user":
            history.append(Turn("user", message["content"]))
        else:
            resp_obj = message.get("response")
            history.append(Turn("assistant", message["content"],
                                resp_obj.as_turns()[1].departments if resp_obj else []))

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Working on it...", expanded=True) as status:
            try:
                resp = asyncio.run(handle_query(prompt, st.session_state.employee_id,
                                                history=history, progress=st.write))
            except Exception as exc:
                status.update(label="Something went wrong", state="error")
                st.error(f"Sorry, the request failed: {exc}")
                st.stop()
            status.update(label=f"Done in {resp.timings['total']:.1f}s",
                          state="complete", expanded=False)

    st.session_state.messages.append(
        {"role": "assistant", "content": resp.final_answer, "response": resp})
    st.rerun()   # redraw so the sidebar picks up new tickets and session totals