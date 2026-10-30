"""Token usage and cost tracking."""
from dataclasses import dataclass

from autogen_core.models import ChatCompletionClient

# USD per 1M tokens: (input, output). Prices change: verify on OpenAI's pricing page.
PRICING_PER_1M = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
}


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.prompt_tokens + other.prompt_tokens,
                     self.completion_tokens + other.completion_tokens,
                     self.calls + other.calls)

    def cost_usd(self, model: str) -> float | None:
        """Estimated cost, or None if the model has no configured price.
        Cached input tokens aren't reported separately, so this is an upper bound."""
        price = PRICING_PER_1M.get(model)
        if price is None:
            return None
        input_price, output_price = price
        return (self.prompt_tokens * input_price + self.completion_tokens * output_price) / 1_000_000


def usage_from_messages(messages: list) -> Usage:
    """Sums usage across an agent run. Each LLM call's usage is attached to the
    message it produced (tool call requests, structured outputs, final replies)."""
    usage = Usage()
    for message in messages:
        mu = getattr(message, "models_usage", None)
        if mu:
            usage.prompt_tokens += mu.prompt_tokens
            usage.completion_tokens += mu.completion_tokens
            usage.calls += 1
    return usage


def usage_from_client(client: ChatCompletionClient, calls: int | None = None) -> Usage:
    """Everything this client has spent since it was created. The client doesn't
    count calls, so pass them in; by default, 1 if any tokens were used, else 0."""
    total = client.total_usage()
    usage = Usage(total.prompt_tokens, total.completion_tokens)
    usage.calls = calls if calls is not None else (1 if usage.total_tokens else 0)
    return usage


def fmt_cost(cost: float | None) -> str:
    return "n/a" if cost is None else f"${cost:.5f}"