"""The web backend, called directly through httpx2 (no browser, no network)."""

from contextlib import asynccontextmanager

import httpx2

from kosik_assistant.assistant import open_backend
from kosik_assistant.profile import Profile
from kosik_assistant.web import create_app


@asynccontextmanager
async def web_client(fake_llm):
    """The app with a scripted model; lifespan run here so MCP opens and closes in one task."""
    app = create_app(lambda: open_backend(fake_llm.client(), Profile()))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_the_page_is_served(fake_llm):
    async with web_client(fake_llm) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Košík asistent" in response.text


async def test_chat_returns_answer_events_and_cart(fake_llm):
    fake_llm.call_tools(("kosik__add_to_cart", {"items": [{"product_id": "p01", "quantity": 2}]}))
    fake_llm.say("Přidal jsem 2× mléko.")

    async with web_client(fake_llm) as client:
        response = await client.post("/api/chat", json={"session_id": "a", "message": "2 mléka"})

    data = response.json()
    assert data["answer"] == "Přidal jsem 2× mléko."
    assert data["events"][0]["kind"] == "tool_call"
    assert data["cart"]["items"][0]["name"] == "Polotučné mléko"


async def test_each_session_has_its_own_conversation(fake_llm):
    fake_llm.say("Ahoj A")
    fake_llm.say("Ahoj B")

    async with web_client(fake_llm) as client:
        await client.post("/api/chat", json={"session_id": "a", "message": "Ahoj, jsem A"})
        await client.post("/api/chat", json={"session_id": "b", "message": "Ahoj, jsem B"})

    second = [m["content"] for m in fake_llm.requests[1]["messages"] if m["role"] == "user"]
    assert second == ["Ahoj, jsem B"]  # B's conversation doesn't contain A's message


async def test_empty_messages_are_rejected(fake_llm):
    async with web_client(fake_llm) as client:
        response = await client.post("/api/chat", json={"session_id": "a", "message": ""})

    assert response.status_code == 422  # validation error from the ChatRequest model
