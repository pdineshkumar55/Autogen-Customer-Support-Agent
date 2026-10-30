"""Detects replies that describe an action instead of performing it."""
import re

# "I'll submit...", "Let me book...", "Submitting now...", "Processing the request..."
NARRATED_ACTION = re.compile(
    r"\b(i['’]ll|i will|let me|i['’]m going to|i am going to)\s+(now\s+)?"
    r"(submit|apply|book|reset|request|process|create|raise|provision|escalate)\b"
    r"|\b(submitting|processing|booking|resetting|creating|applying)\b[^.\n]*(\bnow\b|\.\.\.)",
    re.IGNORECASE,
)

RETRY_NUDGE = (
    "Your last reply described an action, but you did not call a tool, so nothing "
    "actually happened. If the action is still needed, call the tool now. Then write "
    "your final reply describing only what was actually done. Do not repeat actions "
    "that already succeeded."
)


def narrates_action(text: str) -> bool:
    return bool(NARRATED_ACTION.search(text))