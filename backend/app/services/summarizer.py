"""AI summarization service."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.schemas import Article, GeminiSummary, SummaryStatus

logger = logging.getLogger(__name__)
WHITESPACE_PATTERN = re.compile(r"\s+")
SUMMARY_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "main_event": {"type": "STRING"},
        "regional_sentiment": {"type": "NUMBER"},
        "situation_report": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
    "required": ["main_event", "regional_sentiment", "situation_report"],
}


class AIUnavailableError(RuntimeError):
    """Raised when the summarizer cannot produce a real AI result."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(slots=True)
class SummaryExecutionResult:
    summary: GeminiSummary
    status: SummaryStatus


def build_summary_prompt(country_name: str, from_date: str, articles: list[Article], settings: Settings) -> str:
    """Build a strict prompt using only the selected representative articles."""
    article_lines = _build_article_lines(articles, settings=settings)

    return (
        "You are Atlas.Intelligence, a geopolitical command-center analyst.\n"
        "Task: Convert the representative article set below into a single strict JSON object.\n"
        "These articles were already ranked and deduplicated for country relevance.\n"
        "Do NOT include markdown, backticks, or commentary outside the JSON.\n"
        "Prefer the dominant cross-source event, not the most dramatic phrasing.\n\n"
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
        "- Keep the main_event under 18 words.\n"
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

    request_url = _build_generate_content_url(settings)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": build_summary_prompt(country_name, from_date, articles, settings)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.7,
            "topK": 20,
            "maxOutputTokens": settings.gemini_max_output_tokens,
            "responseMimeType": "application/json",
            "responseSchema": SUMMARY_RESPONSE_SCHEMA,
        },
    }
    if settings.gemini_thinking_budget >= 0:
        payload["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": settings.gemini_thinking_budget,
        }
    headers = {"x-goog-api-key": settings.gemini_api_key}

    try:
        response = await client.post(request_url, headers=headers, json=payload, timeout=30.0)
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
        usage = _extract_usage(data)
        return SummaryExecutionResult(
            summary=summary,
            status=SummaryStatus(
                status="ok",
                message="AI summarization completed successfully.",
                used_ai=True,
                model=settings.gemini_model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["total_tokens"],
                thoughts_tokens=usage["thoughts_tokens"],
            ),
        )

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


def _build_generate_content_url(settings: Settings) -> str:
    if "{model}" in settings.gemini_api_url:
        return settings.gemini_api_url.format(model=settings.gemini_model)
    return settings.gemini_api_url


def _build_article_lines(articles: list[Article], *, settings: Settings) -> str:
    lines: list[str] = []
    remaining_budget = settings.gemini_prompt_char_budget

    for index, article in enumerate(articles[: settings.summary_article_limit], start=1):
        line = (
            f"{index}. Title: {_compact_text(article.title, settings.gemini_max_title_chars)}\n"
            f"Source: {article.source} via {', '.join(article.providers or [article.provider])}\n"
            f"Published: {article.published_at.isoformat() if article.published_at else 'Unknown'}\n"
            f"Snippet: {_compact_text(article.snippet or 'No snippet available.', settings.gemini_max_snippet_chars)}"
        )
        if lines and len(line) > remaining_budget:
            break
        lines.append(line[:remaining_budget])
        remaining_budget -= len(lines[-1]) + 2
        if remaining_budget <= 0:
            break

    return "\n\n".join(lines)


def _compact_text(text: str, limit: int) -> str:
    compact = WHITESPACE_PATTERN.sub(" ", text).strip()
    if len(compact) <= limit:
        return compact
    trimmed = compact[: max(0, limit - 1)].rstrip(" ,.;:-")
    return f"{trimmed}…"


def _extract_usage(data: dict) -> dict[str, int | None]:
    usage = data.get("usageMetadata", {})
    return {
        "input_tokens": usage.get("promptTokenCount"),
        "output_tokens": usage.get("candidatesTokenCount"),
        "total_tokens": usage.get("totalTokenCount"),
        "thoughts_tokens": usage.get("thoughtsTokenCount"),
    }
