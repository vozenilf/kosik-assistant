"""The customer's profile, and a search tool that always applies it.

The specification's hard rule "allergens and diets from the profile go into every
search" is enforced here, in code: the model cannot forget it.
"""

import dataclasses
import json
from pathlib import Path
from typing import Any

from agent_harness.tools import Tool
from pydantic import BaseModel


class Profile(BaseModel):
    """Preferences the assistant applies automatically (spec FR-6.1, a subset)."""

    household: int = 2
    allergens: list[str] = []  # never in the cart, e.g. ["lepek", "ořechy"]
    diet: list[str] = []  # e.g. ["bez laktózy"]

    def as_text(self) -> str:
        return (
            f"domácnost: {self.household} osoby; "
            f"vyloučené alergeny: {', '.join(self.allergens) or 'žádné'}; "
            f"diety: {', '.join(self.diet) or 'žádné'}"
        )


def load_profile(path: Path) -> Profile:
    """Read the profile JSON (health data: keep the file out of git). No file = defaults."""
    if not path.is_file():
        return Profile()
    return Profile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def with_profile_filters(search: Tool, profile: Profile) -> Tool:
    """The same search tool, but the profile's allergens and diet are always added."""

    async def filtered_search(**arguments: Any) -> Any:
        arguments["allergens"] = sorted(
            set(arguments.get("allergens") or []) | set(profile.allergens)
        )
        arguments["diet"] = sorted(set(arguments.get("diet") or []) | set(profile.diet))
        return await search.function(**arguments)

    return dataclasses.replace(search, function=filtered_search)
