"""The profile, and the search tool that always applies it."""

import json

from agent_harness.tools import Tool

from kosik_assistant.profile import Profile, load_profile, with_profile_filters


def test_missing_file_gives_the_default_profile(tmp_path):
    assert load_profile(tmp_path / "profile.json") == Profile()


def test_profile_is_read_from_json(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"household": 4, "allergens": ["lepek"]}), encoding="utf-8")

    assert load_profile(path) == Profile(household=4, allergens=["lepek"])


async def test_search_always_gets_the_profile_filters():
    received = {}

    async def search(**arguments):
        received.update(arguments)
        return "[]"

    tool = Tool("kosik__search", "Search.", {"type": "object"}, search)
    profile = Profile(allergens=["lepek", "ořechy"], diet=["bez laktózy"])

    await with_profile_filters(tool, profile).function(query="chléb", allergens=["vejce"])

    assert received == {
        "query": "chléb",
        "allergens": ["lepek", "ořechy", "vejce"],  # the model's + the profile's
        "diet": ["bez laktózy"],
    }
