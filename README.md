# kosik-assistant

A prototype of a conversational shopping assistant for [Košík.cz](https://www.kosik.cz),
built from the product specification. The customer writes in Czech - "doplň můj běžný
nákup", "nakup suroviny na svíčkovou pro 4 lidi", "objednej to na zítra ráno" - and the
assistant searches products, fills the cart and walks through checkout using MCP tools.

It does not connect to the real Košík. It uses a fake Košík MCP server included in this
repo (`server.py`, `shop.py`): made-up products and order history, an in-memory cart, and
the tool names from the specification (`search`, `add_to_cart`, `get_cart`,
`order_summary`, `complete_order`, …). It needs no account and cannot place real orders.

Built on [agent-harness](https://github.com/vozenilf/agent-harness) (previous project) (agent loop, tools,
MCP client, approval hook), with the help of AI.

```
browser (chat + cart) ⇄ FastAPI backend ⇄ agent-harness ⇄ LLM (Claude / Ollama)
                                               │
                                               └─ MCP (stdio) ⇄ fake Košík server
```

## What it does
- Product search in Czech; diacritics are optional (`mleko` finds *Mléko*)
- Regular shopping from the order history, with a reason for each item
- Cart with absolute quantities and the amount missing for free delivery
- Checkout: delivery window → order summary → explicit confirmation → order
- Web chat with a cart panel and visible tool calls; a terminal mode as well

## Rules from the specification enforced in code
The system prompt asks the model to follow the specification's rules. Two of them are also
enforced in code, because a model can ignore a prompt or be misled by injected text:

| Rule | Where |
|---|---|
| `complete_order` only after `order_summary` was shown and the customer confirmed | `guard.py`: `OrderGuard`, plugged into the harness's approval hook |
| Allergens and diet from the profile are applied to every search | `profile.py`: `with_profile_filters` wraps the search tool |

## Run it
Requirements: [uv](https://docs.astral.sh/uv/) and a model - Claude (better Czech) or a
local [Ollama](https://ollama.com) model.
```powershell
$env:HARNESS_BASE_URL="https://api.anthropic.com/v1/"
$env:HARNESS_API_KEY="sk-ant-..."
$env:HARNESS_MODEL="claude-haiku-5-5"
copy profile.example.json profile.json      # optional: household, allergens, diet

uv run kosik-web        # then open http://127.0.0.1:8000
uv run kosik-chat       # or chat in the terminal
```
Without the `HARNESS_*` variables it uses the local Ollama model `qwen3.5:4b` (slow on a CPU).
The variables can also live in a gitignored `.env` file: `uv run --env-file .env kosik-web`.

## Tests
```bash
uv run pytest -v        # 31 tests
uv run ruff check . && uv run ruff format --check .
```
- Unit tests: the shop, the order guard, the profile filter.
- Integration tests start the fake Košík MCP server as a separate process and replace the
  model with scripted replies, e.g. the model tries to order before showing a summary
  (refused), then orders after the customer says "ano" (allowed).
- The web backend is tested in memory through `httpx2.ASGITransport`.
- CI (GitHub Actions) runs lint, format check and tests on every push.

## Prototype limits
- Fake Košík server: made-up data, one cart shared by all conversations, no accounts, no
  real orders. The real Košík MCP (`https://mcp.kosik.cz/mcp/`) is remote and requires an
  OAuth login. Connecting it would mean the MCP HTTP transport with OAuth, one connection
  per customer, and some adaptations (the guard's list of cart-changing tools, the cart
  panel's fields). The agent loop, tools layer, guard and profile filter would carry over.
- Not implemented from the MVP: addresses, payment methods (fixed "card on delivery"),
  repeating a past order, product and slot widgets, streaming.
- Conversations are kept in memory and lost on restart; idle conversations are not cleaned up.
- The OpenAI-compatible Claude endpoint is intended for evaluation; production would use
  the native Claude API.

## Next steps
Real Košík MCP over HTTPS with OAuth · order history and reorder · product and
delivery-slot widgets · streaming answers · per-customer session storage · conversation
logging and tool-call metrics.