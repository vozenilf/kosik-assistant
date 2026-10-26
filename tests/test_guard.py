"""The order guard: complete_order only after a shown summary and an explicit yes."""

import pytest

from kosik_assistant.guard import OrderGuard


def user(text):
    return {"role": "user", "content": text}


def calls(*tools):
    """An assistant message asking for these kosik__ tools."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"c{i}",
                "type": "function",
                "function": {"name": f"kosik__{t}", "arguments": "{}"},
            }
            for i, t in enumerate(tools)
        ],
    }


def answer(text):
    return {"role": "assistant", "content": text}


def guard_for(*messages):
    guard = OrderGuard()
    guard.messages = [{"role": "system", "content": "…"}, *messages]
    return guard


SHOWN_SUMMARY = [
    user("Přidej 2 mléka a objednej na zítra ráno"),
    calls("add_to_cart"),
    calls("set_transport_window"),
    calls("order_summary"),
    answer("Shrnutí: … Potvrdíš objednávku?"),
]


@pytest.mark.parametrize("reply", ["ano", "Ano, objednej", "potvrzuji", "jo"])
def test_confirmed_after_a_shown_summary(reply):
    assert guard_for(*SHOWN_SUMMARY, user(reply)).order_confirmed()


@pytest.mark.parametrize("reply", ["ne", "ještě přidej chleba", "kolik to stojí?"])
def test_anything_but_a_clear_yes_is_refused(reply):
    assert not guard_for(*SHOWN_SUMMARY, user(reply)).order_confirmed()


def test_no_summary_means_no_order():
    assert not guard_for(user("objednej"), calls("add_to_cart")).order_confirmed()


def test_summary_in_the_same_turn_is_not_enough():
    # The model shows the summary and immediately orders: the customer never saw it.
    guard = guard_for(user("objednej"), calls("order_summary"))

    assert not guard.order_confirmed()


def test_a_cart_change_after_the_summary_needs_a_new_summary():
    guard = guard_for(*SHOWN_SUMMARY, user("ano, ale přidej ještě chleba"), calls("add_to_cart"))

    assert not guard.order_confirmed()


async def test_other_tools_are_always_allowed():
    class FakeTool:
        name = "kosik__add_to_cart"

    assert await guard_for(user("přidej mléko"))(FakeTool(), "{}")
