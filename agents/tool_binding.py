import functools
import inspect
from typing import Callable


def bind_employee(func: Callable, employee_id: str) -> Callable:
    """Returns a copy of the tool with employee_id fixed and hidden from the LLM.
    Tools without an employee_id parameter are returned unchanged."""
    sig = inspect.signature(func)
    if "employee_id" not in sig.parameters:
        return func

    @functools.wraps(func)
    def wrapper(**kwargs):
        return func(employee_id=employee_id, **kwargs)

    # AutoGen builds the tool schema from the signature, so drop employee_id from it
    wrapper.__signature__ = sig.replace(
        parameters=[p for name, p in sig.parameters.items() if name != "employee_id"]
    )
    return wrapper