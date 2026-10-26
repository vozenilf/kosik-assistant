"""A small web chat: FastAPI backend + one HTML page.

One process, one Košík MCP connection (opened in the lifespan), one Harness per
browser session. Matches the specification's architecture: client ⇄ backend
(orchestration) ⇄ LLM + Košík MCP.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from agent_harness.harness import Harness
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from openai import APIError
from pydantic import BaseModel, Field

from kosik_assistant.assistant import Backend, open_backend

INDEX_HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    events: list[dict[str, str]]  # what the assistant did: tool calls and results
    cart: dict[str, Any]


def create_app(
    backend_factory: Callable[[], AbstractAsyncContextManager[Backend]] = open_backend,
) -> FastAPI:
    """Build the app. Tests pass a factory that uses a fake model."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        async with backend_factory() as backend:  # MCP connection lives as long as the app
            app.state.backend = backend
            app.state.sessions = {}
            yield

    app = FastAPI(title="Košík asistent", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return INDEX_HTML

    @app.post("/api/chat")
    async def chat(request: ChatRequest) -> ChatResponse:
        backend: Backend = app.state.backend
        sessions: dict[str, Harness] = app.state.sessions
        if request.session_id not in sessions:
            sessions[request.session_id] = backend.new_harness()
        harness = sessions[request.session_id]

        events: list[dict[str, str]] = []
        harness.on_event = lambda kind, text: events.append({"kind": kind, "text": text})
        try:
            answer = await harness.ask(request.message)
        except APIError as error:
            answer = f"Omlouvám se, jazykový model teď není dostupný ({error})."
        return ChatResponse(answer=answer, events=events, cart=await backend.cart())

    @app.get("/api/cart")
    async def cart() -> dict[str, Any]:
        return await app.state.backend.cart()

    return app


def main() -> None:
    """Entry point of `kosik-web`: open http://127.0.0.1:8000 in the browser."""
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
