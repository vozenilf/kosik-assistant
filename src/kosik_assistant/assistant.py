"""The shopping assistant: agent-harness + Košík MCP + the specification's rules.

open_backend() connects to the Košík MCP server once; Backend.new_harness() then
creates one Harness (one conversation) per customer.
"""

import json
import sys
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_harness.config import ModelConfig, load_model_config
from agent_harness.harness import EventHandler, Harness
from agent_harness.mcp_client import ServerConfig, connect_servers
from agent_harness.tools import ToolRegistry
from openai import AsyncOpenAI

from kosik_assistant.guard import OrderGuard
from kosik_assistant.profile import Profile, load_profile, with_profile_filters

KOSIK = "kosik"  # the server's name, so its tools are kosik__search, kosik__add_to_cart, ...
PROFILE_FILE = Path("profile.json")  # gitignored: allergies are health data

# Our fake server, started with the same Python. The real Košík MCP is remote
# (https://mcp.kosik.cz/mcp/, OAuth login) and would need an HTTP transport instead.
FAKE_KOSIK = ServerConfig(command=sys.executable, args=["-m", "kosik_assistant.server"])

SYSTEM_PROMPT = """Jsi osobní nákupní asistent Košíku. Mluvíš česky, tykáš, \
odpovídáš stručně a věcně.
Odpovídej prostým textem bez markdownu (žádné tabulky ani **tučné písmo**); \
položky piš jako řádky s pomlčkou.

Tvrdá pravidla:
- Nevymýšlej produkty, ceny, dostupnost ani termíny. Vše ověř nástrojem.
- Do košíku přidávej jen product_id získaná z nástrojů.
- Jednotlivé nebo nejasné položky nejdřív navrhni (název, balení, cena) a počkej na souhlas.
- Hromadné požadavky (recept, příležitost, běžný nákup) ber jako souhlas: přidej vše jedním \
voláním add_to_cart, ukaž košík a shrň výběr.
- Při chybě nástroje zavolej nástroj, který ji řeší (např. chybí termín → \
get_transport_windows), místo omluvy.
- complete_order volej jen po order_summary a výslovném potvrzení zákazníka \
("ano", "objednej", "potvrzuji").

Běžný nákup: get_frequent_products, u každé položky uveď důvod (jak často a kdy naposledy).
Recept: rozlož jídlo na suroviny, přepočítej na počet porcí, zaokrouhli na balení.
Doprava zdarma od 1500 Kč: podle get_cart řekni, kolik chybí, a navrhni položky z běžného nákupu.
Pokladna: get_cart → get_transport_windows → set_transport_window → order_summary → \
"Potvrdíš objednávku?" → po potvrzení complete_order.

Profil zákazníka: {profile}
Alergeny a diety z profilu se do každého vyhledávání přidávají automaticky."""


@dataclass
class Backend:
    """Everything shared by all conversations: model client, Košík tools, profile."""

    client: AsyncOpenAI
    config: ModelConfig
    tools: ToolRegistry
    profile: Profile

    def new_harness(self, on_event: EventHandler | None = None) -> Harness:
        """One conversation, with the order guard watching it."""
        guard = OrderGuard()
        harness = Harness(
            self.client,
            self.config,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT.format(profile=self.profile.as_text()),
            on_event=on_event,
            approve=guard,
        )
        guard.attach(harness)
        return harness

    async def cart(self) -> dict[str, Any]:
        """The current cart, straight from the shop (no model involved)."""
        return json.loads(await self.tools.call(f"{KOSIK}__get_cart", "{}"))


@asynccontextmanager
async def open_backend(
    client: AsyncOpenAI | None = None,
    profile: Profile | None = None,
    server: ServerConfig = FAKE_KOSIK,
) -> AsyncGenerator[Backend]:
    """Connect to the Košík MCP server; disconnect when the block ends.

    Every argument has a production default; tests pass a fake model client.
    """
    config = load_model_config()
    client = client or AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)
    profile = profile or load_profile(PROFILE_FILE)
    async with AsyncExitStack() as stack:
        tools = await connect_servers({KOSIK: server}, stack)
        if not tools:
            raise RuntimeError("the Košík MCP server did not start")
        tools = [
            with_profile_filters(tool, profile) if tool.name == f"{KOSIK}__search" else tool
            for tool in tools
        ]
        yield Backend(client, config, ToolRegistry(tools), profile)
