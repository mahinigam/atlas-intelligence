import asyncio

import httpx

from app.config import Settings
from app.schemas import Article
from app.services.summarizer import AIUnavailableError, build_summary_prompt, summarize_articles


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
        Settings(),
    )

    assert '"main_event"' in prompt
    assert '"regional_sentiment"' in prompt
    assert '"situation_report"' in prompt
    assert "United States" in prompt
    assert "gnews, newsdata" in prompt
    assert "main_event" in prompt


def test_prompt_compacts_long_article_text() -> None:
    prompt = build_summary_prompt(
        "India",
        "2026-03-20",
        [
            Article(
                title="India " + ("infrastructure " * 20),
                source="Atlas Wire",
                provider="gnews",
                providers=["gnews"],
                url="https://example.com",
                snippet=" ".join(["Long snippet"] * 100),
            )
        ],
        Settings(gemini_max_title_chars=50, gemini_max_snippet_chars=80, gemini_prompt_char_budget=400),
    )

    assert len(prompt) < 1400
    assert "Long snippet Long snippet Long snippet" in prompt
    assert "Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet Long snippet" not in prompt
    assert "L…" in prompt


def test_summarizer_requires_configured_ai() -> None:
    async def run() -> None:
        async with httpx.AsyncClient() as client:
            await summarize_articles(
                client=client,
                settings=Settings(gemini_api_key=None),
                country_name="United States",
                from_date="2026-03-20",
                articles=[
                    Article(
                        title="Infrastructure response expands",
                        source="Atlas Wire",
                        provider="gnews",
                        providers=["gnews"],
                        url="https://example.com",
                        snippet="Authorities expand emergency support and announce transport repairs.",
                    )
                ],
            )

    try:
        asyncio.run(run())
    except AIUnavailableError as exc:
        assert exc.status_code == 503
        assert str(exc) == "Gemini API key is not configured."
    else:
        raise AssertionError("Expected summarize_articles to require a configured AI key")
