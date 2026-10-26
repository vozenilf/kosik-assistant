"""An in-memory stand-in for Košík: catalogue, order history, cart and checkout.

Made-up products and prices. The fake MCP server (server.py) exposes these methods as
tools with the names from the specification, so the assistant works exactly as it
would against the real Košík MCP - without an account, and without real orders.
"""

import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

FREE_DELIVERY_FROM = 1500  # Kč
DELIVERY_FEE = 69  # Kč


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    package: str  # what one piece is, e.g. "1 l", "500 g"
    price: float  # Kč per piece
    allergens: frozenset[str] = frozenset()
    diets: frozenset[str] = frozenset()
    promo: bool = False


def _p(pid, name, category, package, price, allergens=(), diets=(), promo=False):
    """Shorthand for the catalogue below."""
    return Product(
        pid, name, category, package, price, frozenset(allergens), frozenset(diets), promo
    )


CATALOGUE = [
    _p("p01", "Polotučné mléko", "mléčné", "1 l", 24.9, ["mléko"]),
    _p("p02", "Mléko bez laktózy", "mléčné", "1 l", 32.9, ["mléko"], ["bez laktózy"]),
    _p("p03", "Máslo 82 %", "mléčné", "250 g", 54.9, ["mléko"], promo=True),
    _p("p04", "Bílý jogurt", "mléčné", "150 g", 14.9, ["mléko"]),
    _p("p05", "Smetana ke šlehání 31 %", "mléčné", "250 ml", 34.9, ["mléko"]),
    _p("p06", "Eidam 30 % plátky", "mléčné", "100 g", 29.9, ["mléko"]),
    _p("p07", "Vejce M", "vejce", "10 ks", 59.9, ["vejce"]),
    _p("p08", "Chléb konzumní", "pečivo", "1 kg", 44.9, ["lepek"]),
    _p("p09", "Rohlík tukový", "pečivo", "1 ks", 3.9, ["lepek"]),
    _p("p10", "Bezlepkový chléb", "pečivo", "300 g", 79.9, [], ["bezlepkové"]),
    _p("p11", "Houskový knedlík", "pečivo", "400 g", 34.9, ["lepek", "vejce"]),
    _p("p12", "Hovězí zadní", "maso", "500 g", 189.9),
    _p("p13", "Kuřecí prsa", "maso", "500 g", 129.9, promo=True),
    _p("p14", "Mrkev", "zelenina", "1 kg", 19.9, [], ["vegan", "bezlepkové"]),
    _p("p15", "Petržel kořen", "zelenina", "250 g", 24.9, [], ["vegan", "bezlepkové"]),
    _p("p16", "Celer bulva", "zelenina", "1 ks", 29.9, ["celer"], ["vegan", "bezlepkové"]),
    _p("p17", "Cibule žlutá", "zelenina", "1 kg", 17.9, [], ["vegan", "bezlepkové"]),
    _p("p18", "Banány", "ovoce", "1 kg", 34.9, [], ["vegan", "bezlepkové"]),
    _p("p19", "Citron", "ovoce", "1 ks", 9.9, [], ["vegan", "bezlepkové"]),
    _p("p20", "Brusinky kompot", "trvanlivé", "350 g", 49.9, [], ["vegan"]),
    _p("p21", "Müsli s ořechy", "trvanlivé", "500 g", 69.9, ["lepek", "ořechy"]),
    _p("p22", "Ovesné vločky bezlepkové", "trvanlivé", "500 g", 59.9, [], ["bezlepkové"]),
    _p("p23", "Pivo ležák 12°", "nápoje", "0,5 l", 26.9, ["lepek"], promo=True),
    _p("p24", "Neperlivá voda", "nápoje", "1,5 l", 14.9, [], ["vegan", "bezlepkové"]),
]
PRODUCTS = {product.id: product for product in CATALOGUE}

# The customer's earlier orders (product id -> quantity), newest first: the source for
# "doplň můj běžný nákup" (top up my usual shopping).
ORDER_HISTORY = [
    {"days_ago": 7, "items": {"p01": 2, "p08": 1, "p18": 1, "p07": 1, "p23": 6}},
    {"days_ago": 14, "items": {"p01": 2, "p08": 1, "p04": 4, "p23": 6}},
    {"days_ago": 21, "items": {"p01": 3, "p08": 1, "p18": 1, "p07": 1}},
    {"days_ago": 28, "items": {"p01": 2, "p03": 1, "p18": 1}},
]


def normalize(text: str) -> str:
    """Lower case without diacritics, so "mleko" finds "Mléko"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def product_info(product: Product) -> dict:
    return {
        "product_id": product.id,
        "name": product.name,
        "package": product.package,
        "price": product.price,
        "allergens": sorted(product.allergens),
        "diets": sorted(product.diets),
        "promo": product.promo,
    }


@dataclass
class Shop:
    """One customer's shop session: their cart, delivery window and placed orders."""

    cart: dict[str, int] = field(default_factory=dict)  # product id -> quantity
    window: str | None = None
    orders: list[dict] = field(default_factory=list)

    def search(
        self,
        query: str,
        allergens: list[str] | None = None,
        diet: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Products matching every word of the query, without the given allergens."""
        words = normalize(query).split()
        excluded = {normalize(a) for a in allergens or []}
        required = {normalize(d) for d in diet or []}
        found = []
        for product in CATALOGUE:
            text = normalize(f"{product.name} {product.category}")
            if not all(word in text for word in words):
                continue
            if excluded & {normalize(a) for a in product.allergens}:
                continue
            if not required <= {normalize(d) for d in product.diets}:
                continue
            found.append(product_info(product))
        return found[:limit]

    def frequent_products(self, min_purchase_count: int = 2) -> list[dict]:
        """What the customer buys regularly, with how often and when they last bought it."""
        stats: dict[str, dict] = {}
        for order in ORDER_HISTORY:
            for product_id, quantity in order["items"].items():
                entry = stats.setdefault(
                    product_id, {"times": 0, "usual_quantity": quantity, "last": order["days_ago"]}
                )
                entry["times"] += 1
                entry["last"] = min(entry["last"], order["days_ago"])
        return [
            {
                **product_info(PRODUCTS[pid]),
                "bought_in_orders": f"{s['times']} of {len(ORDER_HISTORY)}",
                "usual_quantity": s["usual_quantity"],
                "last_bought_days_ago": s["last"],
            }
            for pid, s in sorted(stats.items(), key=lambda item: -item[1]["times"])
            if s["times"] >= min_purchase_count
        ]

    def add_to_cart(self, items: list[dict]) -> dict:
        """Set absolute quantities; 0 removes the item. Unknown ids are refused."""
        for item in items:
            if item["product_id"] not in PRODUCTS:
                raise ValueError(f"unknown product_id {item['product_id']!r}; use search first")
            if item["quantity"] < 0:
                raise ValueError("quantity cannot be negative")
        for item in items:
            if item["quantity"] == 0:
                self.cart.pop(item["product_id"], None)
            else:
                self.cart[item["product_id"]] = item["quantity"]
        return self.get_cart()

    def get_cart(self) -> dict:
        lines = [
            {
                "product_id": pid,
                "name": PRODUCTS[pid].name,
                "package": PRODUCTS[pid].package,
                "quantity": quantity,
                "line_total": round(PRODUCTS[pid].price * quantity, 2),
            }
            for pid, quantity in self.cart.items()
        ]
        subtotal = round(sum(line["line_total"] for line in lines), 2)
        free = subtotal >= FREE_DELIVERY_FROM
        return {
            "items": lines,
            "subtotal": subtotal,
            "delivery_fee": 0 if free or not lines else DELIVERY_FEE,
            "missing_for_free_delivery": 0 if free else round(FREE_DELIVERY_FROM - subtotal, 2),
        }

    def transport_windows(self) -> list[dict]:
        tomorrow = date.today() + timedelta(days=1)
        return [
            {
                "window_id": f"{tomorrow.isoformat()}-{slot}",
                "date": tomorrow.isoformat(),
                "time": slot,
            }
            for slot in ("08-10", "12-14", "18-20")
        ]

    def set_transport_window(self, window_id: str) -> str:
        if window_id not in {w["window_id"] for w in self.transport_windows()}:
            raise ValueError(f"unknown window_id {window_id!r}; use get_transport_windows")
        self.window = window_id
        return f"delivery window set: {window_id}"

    def order_summary(self) -> dict:
        cart = self.get_cart()
        if not cart["items"]:
            raise ValueError("the cart is empty")
        if self.window is None:
            raise ValueError("no delivery window chosen; use get_transport_windows")
        return {
            **cart,
            "delivery_window": self.window,
            "payment": "card on delivery",
            "total": round(cart["subtotal"] + cart["delivery_fee"], 2),
        }

    def complete_order(self) -> dict:
        summary = self.order_summary()  # same checks: cart and window must be ready
        order = {"order_id": f"K{1000 + len(self.orders) + 1}", **summary}
        self.orders.append(order)
        self.cart.clear()
        self.window = None
        return order
