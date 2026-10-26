"""The in-memory shop behind the fake Košík MCP server."""

import pytest

from kosik_assistant.shop import DELIVERY_FEE, FREE_DELIVERY_FROM, PRODUCTS


def names(products):
    return [p["name"] for p in products]


def test_search_ignores_case_and_diacritics(shop):
    assert names(shop.search("MLEKO")) == ["Polotučné mléko", "Mléko bez laktózy"]


def test_search_excludes_allergens(shop):
    assert names(shop.search("chléb", allergens=["lepek"])) == ["Bezlepkový chléb"]


def test_search_requires_every_diet(shop):
    assert names(shop.search("mléko", diet=["bez laktózy"])) == ["Mléko bez laktózy"]


def test_frequent_products_come_from_the_order_history(shop):
    frequent = {p["name"]: p for p in shop.frequent_products()}

    assert "Polotučné mléko" in frequent
    assert frequent["Polotučné mléko"]["bought_in_orders"] == "4 of 4"
    assert frequent["Polotučné mléko"]["last_bought_days_ago"] == 7
    assert "Kuřecí prsa" not in frequent  # never bought


def test_add_to_cart_sets_absolute_quantities_and_zero_removes(shop):
    shop.add_to_cart([{"product_id": "p01", "quantity": 2}, {"product_id": "p08", "quantity": 1}])
    shop.add_to_cart([{"product_id": "p01", "quantity": 3}, {"product_id": "p08", "quantity": 0}])

    assert shop.cart == {"p01": 3}


def test_unknown_products_are_refused_and_nothing_changes(shop):
    with pytest.raises(ValueError, match="unknown product_id"):
        shop.add_to_cart([{"product_id": "p01", "quantity": 1}, {"product_id": "x", "quantity": 1}])
    assert shop.cart == {}  # checked first, so the valid item wasn't added either


def test_cart_shows_what_is_missing_for_free_delivery(shop):
    shop.add_to_cart([{"product_id": "p12", "quantity": 2}])  # 2 × 189.90

    cart = shop.get_cart()

    assert cart["subtotal"] == 379.8
    assert cart["delivery_fee"] == DELIVERY_FEE
    assert cart["missing_for_free_delivery"] == round(FREE_DELIVERY_FROM - 379.8, 2)


def test_delivery_is_free_above_the_threshold(shop):
    shop.add_to_cart([{"product_id": "p12", "quantity": 8}])  # 1519.20 Kč

    assert shop.get_cart()["delivery_fee"] == 0


def test_summary_needs_a_delivery_window(shop):
    shop.add_to_cart([{"product_id": "p01", "quantity": 1}])
    with pytest.raises(ValueError, match="no delivery window"):
        shop.order_summary()

    shop.set_transport_window(shop.transport_windows()[0]["window_id"])

    assert shop.order_summary()["total"] == PRODUCTS["p01"].price + DELIVERY_FEE


def test_unknown_delivery_windows_are_refused(shop):
    with pytest.raises(ValueError, match="unknown window_id"):
        shop.set_transport_window("2020-01-01-08-10")  # an old date: not offered
    assert shop.window is None  # nothing was set


def test_complete_order_places_it_and_empties_the_cart(shop):
    shop.add_to_cart([{"product_id": "p01", "quantity": 1}])
    shop.set_transport_window(shop.transport_windows()[0]["window_id"])

    order = shop.complete_order()

    assert order["order_id"] == "K1001"
    assert shop.cart == {}
    assert shop.orders == [order]
