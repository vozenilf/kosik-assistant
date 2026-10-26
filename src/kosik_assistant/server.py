"""A fake Košík MCP server: the Shop's methods as MCP tools, over stdio.

Tool names and parameters follow chapter 6 of the specification (a subset: search,
regular shopping, cart, delivery window, summary, order). Swapping it for the real
Košík MCP server would only change the connection, not the assistant.
"""

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from kosik_assistant.shop import Shop

READ_ONLY = ToolAnnotations(read_only_hint=True)

server = MCPServer(
    "kosik",
    instructions="Fake Košík grocery shop: search products, manage the cart, check out.",
)
shop = Shop()  # one shop session per server process


class CartItem(BaseModel):
    product_id: str
    quantity: int  # the resulting quantity: 0 removes the item


def shop_errors(action: Callable[[], Any]) -> Any:
    """Run a shop action; turn its ValueError into a ToolError the client can read."""
    try:
        return action()
    except ValueError as error:
        raise ToolError(str(error)) from error


@server.tool(annotations=READ_ONLY)
def search(
    query: str,
    allergens: list[str] | None = None,
    diet: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search products by name or category (Czech, diacritics optional).

    allergens: exclude products containing any of these (e.g. "lepek", "ořechy").
    diet: only products with all of these (e.g. "bezlepkové", "vegan", "bez laktózy").
    """
    return shop.search(query, allergens, diet, limit)


@server.tool(annotations=READ_ONLY)
def get_frequent_products(min_purchase_count: int = 2) -> list[dict]:
    """Products the customer buys regularly, with how often and when last bought."""
    return shop.frequent_products(min_purchase_count)


@server.tool(annotations=READ_ONLY)
def get_cart() -> dict:
    """The cart: items, subtotal, delivery fee and how much is missing for free delivery."""
    return shop.get_cart()


@server.tool()
def add_to_cart(items: list[CartItem]) -> dict:
    """Set quantities in the cart in one call. quantity is the resulting amount; 0 removes."""
    return shop_errors(lambda: shop.add_to_cart([item.model_dump() for item in items]))


@server.tool(annotations=READ_ONLY)
def get_transport_windows() -> list[dict]:
    """Available delivery windows."""
    return shop.transport_windows()


@server.tool()
def set_transport_window(window_id: str) -> str:
    """Choose a delivery window (window_id from get_transport_windows)."""
    return shop_errors(lambda: shop.set_transport_window(window_id))


@server.tool(annotations=READ_ONLY)
def order_summary() -> dict:
    """Summary before ordering: items, delivery window, payment, total. Show it to the user."""
    return shop_errors(shop.order_summary)


@server.tool(annotations=ToolAnnotations(destructive_hint=True))
def complete_order() -> dict:
    """Place the order. Only after order_summary and the customer's explicit confirmation."""
    return shop_errors(shop.complete_order)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
