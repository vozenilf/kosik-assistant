"""The whole assistant with the real fake Košík server and a scripted model.

Integration tests: open_backend() starts the fake Košík MCP server as a separate
process, so these check the real wiring - tools, profile filter, order guard.
"""

import json

from agent_harness.harness import DECLINED

from kosik_assistant.assistant import open_backend
from kosik_assistant.profile import Profile
from kosik_assistant.shop import Shop

MILK = {"items": [{"product_id": "p01", "quantity": 2}]}
WINDOW = {"window_id": Shop().transport_windows()[0]["window_id"]}  # tomorrow 08-10


async def test_the_profile_filters_every_search(fake_llm):
    fake_llm.call_tools(("kosik__search", {"query": "chléb"}))
    fake_llm.say("Mám pro tebe bezlepkový chléb.")

    async with open_backend(fake_llm.client(), Profile(allergens=["lepek"])) as backend:
        await backend.new_harness().ask("Chci chleba")

    found = fake_llm.tool_results()[0]
    assert "Bezlepkový chléb" in found
    assert "Chléb konzumní" not in found  # contains gluten: filtered although not asked for


async def test_no_order_without_a_shown_summary_and_a_yes(fake_llm):
    # Turn 1: the model rushes - fills the cart and orders in one go.
    fake_llm.call_tools(("kosik__add_to_cart", MILK), ("kosik__set_transport_window", WINDOW))
    fake_llm.call_tools(("kosik__order_summary", {}), ("kosik__complete_order", {}))
    fake_llm.say("Tady je shrnutí. Potvrdíš objednávku?")
    # Turn 2: the customer confirms; now the order may go through.
    fake_llm.call_tools(("kosik__complete_order", {}))
    fake_llm.say("Objednávka K1001 je odeslána.")

    async with open_backend(fake_llm.client(), Profile()) as backend:
        harness = backend.new_harness()

        await harness.ask("Dvě mléka na zítra ráno a objednej")
        first_turn = fake_llm.tool_results()
        cart_after_first_turn = await backend.cart()

        await harness.ask("ano")
        cart_at_the_end = await backend.cart()

    assert first_turn[-1] == DECLINED  # complete_order refused: the summary wasn't shown yet
    assert cart_after_first_turn["items"][0]["quantity"] == 2  # nothing ordered yet
    assert json.loads(fake_llm.tool_results()[-1])["order_id"] == "K1001"  # turn 2: ordered
    assert cart_at_the_end["items"] == []  # the order emptied the cart
