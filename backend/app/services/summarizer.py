"""AI summarization service — summarizes ranked headline articles with explicit status handling."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.schemas import Article, GeminiSummary, SummaryStatus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SummaryExecutionResult:
    summary: GeminiSummary
    status: SummaryStatus


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
) -> SummaryExecutionResult:
    """Summarize ranked headline articles and return both content and execution state."""
    if not articles:
        return SummaryExecutionResult(
            summary=_placeholder_summary(country_name, from_date, reason="no_articles"),
            status=SummaryStatus(
                status="raw_only",
                message="No representative articles were available for AI summarization.",
                used_ai=False,
            ),
        )

    if not settings.gemini_api_key:
        return SummaryExecutionResult(
            summary=_placeholder_summary(country_name, from_date, reason="no_api_key"),
            status=SummaryStatus(
                status="unconfigured",
                message="Gemini API key is not configured. Showing raw news only.",
                used_ai=False,
            ),
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
        summary = GeminiSummary.model_validate(parsed)
        return SummaryExecutionResult(
            summary=summary,
            status=SummaryStatus(
                status="ok",
                message="AI summarization completed successfully.",
                used_ai=True,
            ),
        )

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.error("Gemini HTTP %s: %s", status_code, exc.response.text[:300])
        if status_code == 429:
            return SummaryExecutionResult(
                summary=_placeholder_summary(country_name, from_date, reason="quota"),
                status=SummaryStatus(
                    status="quota_exhausted",
                    message="AI summarization is currently unavailable. Showing raw news only.",
                    used_ai=False,
                ),
            )
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned non-JSON: %s", exc)
    except Exception as exc:
        logger.error("Gemini summarization failed: %s", exc)

    return SummaryExecutionResult(
        summary=_placeholder_summary(country_name, from_date, reason="error"),
        status=SummaryStatus(
            status="raw_only",
            message="AI summarizer temporarily unavailable. Showing raw news only.",
            used_ai=False,
        ),
    )


def _strip_code_fences(text_payload: str) -> str:
    cleaned = text_payload.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def _placeholder_summary(
    country_name: str,
    from_date: str,
    *,
    reason: str,
) -> GeminiSummary:
    if reason == "quota":
        return GeminiSummary(
            main_event=f"{country_name} — AI analysis unavailable",
            regional_sentiment=0.0,
            situation_report=[
                "AI summarization is currently unavailable, so Atlas is showing ranked raw reporting only.",
                "Representative articles remain deduplicated, normalized, and country-filtered.",
                f"Historical sweep remains anchored to {from_date}.",
            ],
        )
    if reason == "no_articles":
        return GeminiSummary(
            main_event=f"{country_name} — No representative articles available",
            regional_sentiment=0.0,
            situation_report=[
                "Live providers returned no articles that passed country relevance ranking.",
                "Atlas withheld weakly matched items instead of fabricating a summary.",
                f"Historical sweep remains anchored to {from_date}.",
            ],
        )
    if reason == "no_api_key":
        return GeminiSummary(
            main_event=f"{country_name} — Awaiting Gemini configuration",
            regional_sentiment=0.0,
            situation_report=[
                "Gemini API key is not configured, so Atlas is showing ranked raw reporting only.",
                "Provider results are still normalized, deduplicated, and country-filtered.",
                f"Historical sweep remains anchored to {from_date}.",
            ],
        )

    return GeminiSummary(
        main_event=f"{country_name} — AI analysis temporarily unavailable",
        regional_sentiment=0.0,
        situation_report=[
            "Gemini summarization encountered an error and Atlas fell back to raw ranked reporting.",
            "Representative articles remain deduplicated, normalized, and country-filtered.",
            f"Historical sweep remains anchored to {from_date}.",
        ],
    )
