"""The order guard: complete_order only after order_summary and an explicit "yes".

Specification, chapter 7.2: "complete_order only after order_summary and explicit
confirmation". A prompt can only ask the model to follow this; here the harness's
approval hook enforces it, so no model output can place an unconfirmed order.
"""

import re
from typing import Any

from agent_harness.harness import Harness
from agent_harness.tools import Tool

CONFIRMATION = re.compile(
    r"\b(ano|jo|potvrzuji|potvrzuju|potvrdit|objednej|objednat|souhlasím|yes|confirm)\b",
    re.IGNORECASE,
)
CART_CHANGES = ("add_to_cart", "set_transport_window")


def tool_calls(messages: list[dict[str, Any]]) -> list[tuple[int, str]]:
    """(position in the conversation, tool name) of every tool the model asked for."""
    return [
        (index, call["function"]["name"])
        for index, message in enumerate(messages)
        for call in message.get("tool_calls") or []
    ]


class OrderGuard:
    """An Approver (see agent_harness.harness) that checks the conversation so far."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def attach(self, harness: Harness) -> None:
        """Read this harness's conversation (the same list object, so always current)."""
        self.messages = harness.messages

    async def __call__(self, tool: Tool, arguments: str) -> bool:
        if tool.name.endswith("__complete_order"):
            return self.order_confirmed()
        return True  # cart changes are the normal flow (bulk requests count as consent)

    def order_confirmed(self) -> bool:
        """True only if the customer saw a current summary and then clearly said yes."""
        users = [i for i, m in enumerate(self.messages) if m["role"] == "user"]
        if not users:
            return False
        last_user = users[-1]
        calls = tool_calls(self.messages)
        summaries = [i for i, name in calls if name.endswith("__order_summary")]
        changes = [i for i, name in calls if name.endswith(CART_CHANGES)]

        if not summaries or summaries[-1] > last_user:
            return False  # no summary yet, or not shown to the customer before they replied
        if changes and changes[-1] > summaries[-1]:
            return False  # the cart changed after the summary: it is out of date
        return bool(CONFIRMATION.search(self.messages[last_user]["content"]))
