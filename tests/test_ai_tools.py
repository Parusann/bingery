"""Tests for the shared tool registry."""
from utils.ai_provider import ToolSchema
from utils.ai_tools import ALL_TOOLS, TOOL_NAMES


def test_all_tools_are_tool_schema_instances():
    assert len(ALL_TOOLS) >= 5
    for t in ALL_TOOLS:
        assert isinstance(t, ToolSchema)
        assert t.name
        assert t.description
        assert t.parameters.get("type") == "object"


def test_expected_tool_names_present():
    expected = {
        "search_anime_database",
        "get_user_taste_profile",
        "get_user_watchlist",
        "get_anime_details",
        "search_anilist",
    }
    assert expected.issubset(set(TOOL_NAMES))
