"""Chat with the shopping assistant in the terminal (reuses the harness's CLI loop)."""

import asyncio

from agent_harness.cli import print_event, repl

from kosik_assistant.assistant import open_backend


async def run() -> None:
    async with open_backend() as backend:
        harness = backend.new_harness(on_event=print_event)
        print(f"\nKošík asistent ({backend.config.model}) - profil: {backend.profile.as_text()}")
        print("/quit nebo Ctrl+C ukončí")
        await repl(harness)


def main() -> None:
    try:
        asyncio.run(run())
    except (EOFError, KeyboardInterrupt):
        pass
    print("\nnashledanou!")
