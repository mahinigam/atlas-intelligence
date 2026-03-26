from app.schemas import Article
from app.services.summarizer import build_summary_prompt


def test_prompt_includes_required_json_contract() -> None:
    prompt = build_summary_prompt(
        "United States",
        "2026-03-20",
        [
            Article(
                title="Infrastructure response expands",
                source="Atlas Wire",
                provider="gnews",
                providers=["gnews", "newsdata"],
                url="https://example.com",
                snippet="Authorities expand emergency support and announce transport repairs.",
            )
        ],
    )

    assert '"main_event"' in prompt
    assert '"regional_sentiment"' in prompt
    assert '"situation_report"' in prompt
    assert "United States" in prompt
    assert "gnews, newsdata" in prompt
