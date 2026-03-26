"""AI summarization service."""

from __future__ import annotations

import json
import logging

import httpx

from app.config import Settings
from app.schemas import Article, GeminiSummary

logger = logging.getLogger(__name__)


class AIUnavailableError(RuntimeError):
    """Raised when the summarizer cannot produce a real AI result."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_summary_prompt(country_name: str, from_date: str, articles: list[Article]) -> str:
    """Build a strict prompt using only the selected representative articles."""
    article_lines = "\n".join(
        (
            f"{index + 1}. Title: {article.title}\n"
            f"Source: {article.source} via {', '.join(article.providers or [article.provider])}\n"
            f"Published: {article.published_at.isoformat() if article.published_at else 'Unknown'}\n"
            f"Snippet: {article.snippet or 'No snippet available.'}"
        )
        for index, article in enumerate(articles[:5])
    )

    return (
        "You are Atlas.Intelligence, a geopolitical command-center analyst.\n"
        "Task: Convert the representative article set below into a single strict JSON object.\n"
        "These articles were already ranked and deduplicated for country relevance.\n"
        "Do NOT include markdown, backticks, or commentary outside the JSON.\n\n"
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
        "- Identify the dominant event pattern across all representative articles.\n"
        "- Do NOT repeat article titles as bullets.\n"
        "- If articles conflict, mention uncertainty inside one bullet.\n"
        "- Sentiment: -1 = severe crisis, 0 = neutral, +1 = strongly positive.\n"
        "- Return ONLY the JSON object.\n\n"
        "Representative articles:\n"
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
    """Summarize ranked headline articles and require a real AI response."""
    if not articles:
        raise AIUnavailableError(
            "No representative articles were available for AI summarization.",
            status_code=424,
        )

    if not settings.gemini_api_key:
        raise AIUnavailableError(
            "Gemini API key is not configured.",
            status_code=503,
        )

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

        parsed = json.loads(_strip_code_fences(text_payload))
        return GeminiSummary.model_validate(parsed)

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.error("Gemini HTTP %s: %s", status_code, exc.response.text[:300])
        if status_code == 429:
            raise AIUnavailableError(
                "Gemini quota exhausted.",
                status_code=503,
            )
        raise AIUnavailableError(
            f"Gemini returned HTTP {status_code}.",
            status_code=502,
        ) from exc
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON: %s", exc)
        raise AIUnavailableError(
            "Gemini returned an invalid response payload.",
            status_code=502,
        ) from exc
    except Exception as exc:
        logger.error("Gemini summarization failed: %s", exc)
        raise AIUnavailableError(
            "Gemini summarization failed.",
            status_code=502,
        ) from exc


def _strip_code_fences(text_payload: str) -> str:
    cleaned = text_payload.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()
