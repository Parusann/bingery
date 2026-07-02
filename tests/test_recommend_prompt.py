"""Regression guards for the recommend-mode prompt rewrite."""


def test_recommend_prompt_mandates_similarity_tool_and_evidence():
    from routes.chatbot_tools import build_system_prompt

    p = build_system_prompt("recommend")
    assert "find_similar_anime" in p
    assert "mood_tags" in p  # refinement re-query instruction
    assert "franchise" in p.lower()  # franchise entries are not "similar" picks


def test_word_cap_raised_to_100():
    from routes.chatbot_tools import BINGERY_SYSTEM

    assert "100 words" in BINGERY_SYSTEM
    assert "80 words" not in BINGERY_SYSTEM


def test_rate_and_onboard_modes_removed():
    """Chat is a single recommendation experience; the rate/onboard modes
    were removed. Legacy clients sending old mode values must still get
    the recommend prompt."""
    from routes.chatbot_tools import MODE_PROMPTS, build_system_prompt

    assert set(MODE_PROMPTS) == {"recommend"}
    assert build_system_prompt("rate") == build_system_prompt("recommend")
    assert build_system_prompt("onboard") == build_system_prompt("recommend")
    assert build_system_prompt(None) == build_system_prompt("recommend")
