"""AI summarization service — sends article snippets to Gemini for situation reports."""

from __future__ import annotations

import json
import logging

import httpx

from app.config import Settings
from app.schemas import Article, GeminiSummary

logger = logging.getLogger(__name__)


def build_summary_prompt(country_name: str, from_date: str, articles: list[Article]) -> str:
    """Build a strict zero-shot prompt that produces a JSON situation report."""
    article_lines = "\n".join(
        f"{index + 1}. Title: {article.title}\nSource: {article.source}\nSnippet: {article.snippet or 'No snippet available.'}"
        for index, article in enumerate(articles[:5])
    )

    return (
        "You are Atlas.Intelligence, a geopolitical command-center analyst.\n"
        "Task: Convert the raw article snippets below into a single strict JSON object.\n"
        "Do NOT include any markdown, backticks, or commentary outside the JSON.\n\n"
        f"Country: {country_name}\n"
        f"Historical window start: {from_date}\n\n"
        "Required JSON schema (follow EXACTLY):\n"
        "{\n"
        '  "main_event": "<single concise headline of the dominant event>",\n'
        '  "regional_sentiment": <float between -1.0 and 1.0>,\n'
        '  "situation_report": [\n'
        '    "<bullet 1, max 22 words>",\n'
        '    "<bullet 2, max 22 words>",\n'
        '    "<bullet 3, max 22 words>"\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Identify the DOMINANT event pattern across all articles.\n"
        "- Do NOT repeat article titles as bullets.\n"
        "- If articles conflict, mention uncertainty inside one bullet.\n"
        "- Sentiment: -1 = severe crisis, 0 = neutral, +1 = strongly positive.\n"
        "- Return ONLY the JSON object, nothing else.\n\n"
        "Articles:\n"
        f"{article_lines}"
    )


async def summarize_articles(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    country_name: str,
    from_date: str,
    articles: list[Article],
) -> GeminiSummary:
    """Send articles to Gemini and return a validated summary. Falls back gracefully on errors."""
    if not settings.gemini_api_key:
        return _placeholder_summary(country_name, from_date)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_summary_prompt(country_name, from_date, articles)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "responseMimeType": "application/json",
        },
    }
    headers = {"x-goog-api-key": settings.gemini_api_key}

    try:
        response = await client.post(
            settings.gemini_api_url, headers=headers, json=payload, timeout=30.0
        )
        response.raise_for_status()
        data = response.json()

        text_payload = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "{}")
        )

        # Strip any markdown fences that Gemini sometimes adds despite instructions
        cleaned = text_payload.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        return GeminiSummary.model_validate(parsed)

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Gemini HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
        )
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON: %s", exc)
    except Exception as exc:
        logger.error("Gemini summarization failed: %s", exc)

    return _placeholder_summary(country_name, from_date, error=True)


def _placeholder_summary(
    country_name: str, from_date: str, *, error: bool = False
) -> GeminiSummary:
    """Return a deterministic placeholder when Gemini is unavailable or errored."""
    if error:
        return GeminiSummary(
            main_event=f"{country_name} — AI analysis temporarily unavailable",
            regional_sentiment=0.0,
            situation_report=[
                "Gemini summarization encountered an error and will retry on next request.",
                "News ingestion pipeline is active; raw article data is still available below.",
                f"Historical sweep is anchored to {from_date}.",
            ],
        )

    return GeminiSummary(
        main_event=f"{country_name} — Awaiting Gemini configuration",
        regional_sentiment=0.0,
        situation_report=[
            "Gemini API key is not configured. This is a deterministic placeholder.",
            "News ingestion is active and will produce real summaries once Vertex access is provided.",
            f"Historical analysis is currently anchored to {from_date}.",
        ],
    )
