"""Shared fixtures: the fake model server from agent-harness, plus a fresh shop."""

import json
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI

from kosik_assistant.shop import Shop


class FakeLLM:
    """Plays the model: answers with queued replies and records every request."""

    def __init__(self) -> None:
        self.replies: list[dict[str, Any]] = []
        self.requests: list[dict[str, Any]] = []

    def say(self, content: str) -> None:
        self._queue({"role": "assistant", "content": content}, "stop")

    def call_tools(self, *calls: tuple[str, dict[str, Any]]) -> None:
        tool_calls = [
            {
                "id": f"call_{len(self.replies)}_{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            for i, (name, args) in enumerate(calls)
        ]
        self._queue({"role": "assistant", "content": None, "tool_calls": tool_calls}, "tool_calls")

    def _queue(self, message: dict[str, Any], finish_reason: str) -> None:
        self.replies.append(
            {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "fake-model",
                "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
            }
        )

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        return httpx2.Response(200, json=self.replies.pop(0))

    def client(self) -> AsyncOpenAI:
        return AsyncOpenAI(
            base_url="http://fake-server/v1",
            api_key="test",
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(self.handler)),
        )

    def tool_results(self) -> list[str]:
        """Every tool result the harness sent back, in order (from the last request)."""
        return [m["content"] for m in self.requests[-1]["messages"] if m["role"] == "tool"]


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def shop() -> Shop:
    return Shop()
