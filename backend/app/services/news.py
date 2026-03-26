"""News ingestion service — fetches country-scoped articles from GNews or NewsData.io."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx

from app.config import Settings
from app.country_metadata import get_country_name, get_iso_a2
from app.schemas import Article

logger = logging.getLogger(__name__)

MAX_RETRIES = 1


async def fetch_country_news(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> Sequence[Article]:
    """Try GNews first, fall back to NewsData, then to synthetic placeholder."""
    country_code = country_code.upper()

    if settings.gnews_api_key:
        articles = await _fetch_from_gnews(
            client=client,
            settings=settings,
            country_code=country_code,
            from_date=from_date,
        )
        if articles:
            return articles

    if settings.newsdata_api_key:
        articles = await _fetch_from_newsdata(
            client=client,
            settings=settings,
            country_code=country_code,
            from_date=from_date,
        )
        if articles:
            return articles

    logger.info("No news API keys configured — returning fallback for %s", country_code)
    return _fallback_articles(country_code=country_code, from_date=from_date)


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    *,
    label: str,
) -> dict | None:
    """Execute a GET request with one retry on timeout/5xx errors."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.get(url, params=params, timeout=20.0)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.warning("%s timeout (attempt %d/%d)", label, attempt + 1, MAX_RETRIES + 1)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "%s HTTP %s (attempt %d/%d): %s",
                label,
                exc.response.status_code,
                attempt + 1,
                MAX_RETRIES + 1,
                exc.response.text[:200],
            )
            if exc.response.status_code < 500:
                break  # Don't retry client errors
        except httpx.HTTPError as exc:
            logger.warning("%s network error (attempt %d/%d): %s", label, attempt + 1, MAX_RETRIES + 1, exc)
    return None


async def _fetch_from_gnews(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> list[Article]:
    iso_a2 = get_iso_a2(country_code)
    country_name = get_country_name(country_code)

    params = {
        "apikey": settings.gnews_api_key,
        "country": iso_a2,
        "lang": settings.default_language,
        "max": settings.news_article_limit,
        "from": from_date,
        "q": country_name,
    }

    payload = await _fetch_with_retry(client, settings.gnews_base_url, params, label="GNews")
    if not payload:
        return []

    items: list[Article] = []
    for article in payload.get("articles", [])[: settings.news_article_limit]:
        items.append(
            Article(
                title=article.get("title", "Untitled event"),
                source=article.get("source", {}).get("name", "Unknown Source"),
                url=article.get("url", "#"),
                published_at=article.get("publishedAt"),
                snippet=article.get("description") or article.get("content") or "",
            )
        )
    return items


async def _fetch_from_newsdata(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> list[Article]:
    iso_a2 = get_iso_a2(country_code)

    params = {
        "apikey": settings.newsdata_api_key,
        "country": iso_a2,
        "language": settings.default_language,
        "size": settings.news_article_limit,
        "from_date": from_date,
    }

    payload = await _fetch_with_retry(client, settings.newsdata_base_url, params, label="NewsData")
    if not payload:
        return []

    items: list[Article] = []
    for article in payload.get("results", [])[: settings.news_article_limit]:
        items.append(
            Article(
                title=article.get("title", "Untitled event"),
                source=article.get("source_name", "Unknown Source"),
                url=article.get("link", "#"),
                published_at=article.get("pubDate"),
                snippet=article.get("description") or article.get("content") or "",
            )
        )
    return items


def _fallback_articles(*, country_code: str, from_date: str) -> list[Article]:
    """Generate deterministic placeholder content when no API keys are available."""
    country_name = get_country_name(country_code)
    return [
        Article(
            title=f"{country_name} — Intelligence feed active",
            source="Atlas Synthetic Feed",
            url="https://example.com/atlas-intelligence",
            snippet=(
                f"Connect GNews or NewsData.io credentials to receive live intelligence for {country_name}. "
                f"Current historical sweep start date: {from_date}."
            ),
        ),
        Article(
            title=f"{country_name} — Regional monitoring initialized",
            source="Atlas Synthetic Feed",
            url="https://example.com/atlas-intelligence",
            snippet=(
                f"Atlas.Intelligence is monitoring the {country_name} region. "
                "Real article feeds will replace these synthetic payloads once API keys are configured."
            ),
        ),
        Article(
            title=f"Geopolitical context: {country_name}",
            source="Atlas Synthetic Feed",
            url="https://example.com/atlas-intelligence",
            snippet=(
                f"This placeholder simulates the intelligence pipeline for {country_name}. "
                "Sentiment analysis, situation reports, and main event extraction will activate with live data."
            ),
        ),
    ]
