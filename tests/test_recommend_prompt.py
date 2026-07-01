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


def test_other_modes_do_not_gain_recommendation_behavior():
    from routes.chatbot_tools import MODE_PROMPTS

    assert "find_similar_anime" not in MODE_PROMPTS["rate"]
    assert "find_similar_anime" not in MODE_PROMPTS["onboard"]
