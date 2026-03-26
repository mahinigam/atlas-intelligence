"""News ingestion, normalization, ranking, and provider-health orchestration."""

from __future__ import annotations

import asyncio
import logging
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from html import unescape
from time import perf_counter
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.cache import CacheClient
from app.config import Settings
from app.country_metadata import get_country_info, get_country_name, get_iso_a2
from app.services.source_reputation import get_source_trust_sync
from app.schemas import (
    Article,
    CountryQualitySnapshot,
    HistoricalMetric,
    ObservabilitySnapshot,
    PipelineStatus,
    ProviderMetric,
    ProviderStatus,
    StoryCluster,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
MAX_CATCHALL_POLLS = 3
CATCHALL_POLL_DELAY_SECONDS = 1.2
SUMMARY_FALLBACK_SOURCE = "Atlas Synthetic Feed"
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
BOILERPLATE_PATTERN = re.compile(r"\[\+\d+\s+chars\]|\bread more\b", re.IGNORECASE)
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
DATE_PATTERN = re.compile(r"\b(?:\d{1,2}\s+[A-Z][a-z]+|\b[A-Z][a-z]+\s+\d{1,2}\b|\d{4}-\d{2}-\d{2})")
NUMBER_PATTERN = re.compile(r"\b(?:\d+(?:,\d{3})*(?:\.\d+)?%?)\b")
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "ocid",
    "ref",
    "ref_src",
}

# COUNTRY_SIGNAL_OVERRIDES has been replaced by enriched CountryInfo in country_metadata.py.
# The _country_signals() function now reads directly from CountryInfo fields.

GENERIC_POLITICAL_TERMS = [
    "government",
    "parliament",
    "president",
    "prime minister",
    "cabinet",
    "ministry",
    "election",
    "military",
    "police",
]
CATEGORY_KEYWORDS = {
    "conflict": ["attack", "strike", "military", "troops", "missile", "war", "clash"],
    "politics": ["election", "government", "parliament", "minister", "president", "policy"],
    "economy": ["bank", "inflation", "trade", "market", "economy", "tariff", "investment"],
    "disaster": ["earthquake", "flood", "storm", "wildfire", "disaster", "evacuation"],
    "infrastructure": ["rail", "airport", "road", "bridge", "power", "grid", "transport"],
    "humanitarian": ["aid", "relief", "refugee", "hunger", "hospital", "humanitarian"],
}
CATEGORY_DECAY_HOURS = {
    "conflict": 24 * 10,
    "politics": 24 * 7,
    "economy": 24 * 5,
    "disaster": 24 * 14,
    "infrastructure": 24 * 12,
    "humanitarian": 24 * 10,
    "general": 24 * 7,
}
LOCAL_LANGUAGE_HINTS = {
    "IND": ["en", "hi"],
    "FRA": ["fr", "en"],
    "DEU": ["de", "en"],
    "ESP": ["es", "en"],
    "ITA": ["it", "en"],
    "BRA": ["pt", "en"],
    "CHN": ["zh", "en"],
    "JPN": ["ja", "en"],
    "RUS": ["ru", "en"],
    "ARE": ["ar", "en"],
    "SAU": ["ar", "en"],
    "MEX": ["es", "en"],
    "IDN": ["id", "en"],
}

_PROVIDER_RUNTIME: dict[str, "ProviderRuntimeState"] = {}
PROVIDER_LABELS = {
    "worldnews": "World News API",
    "currents": "Currents API",
    "newscatcher": "NewsCatcher CatchAll",
    "newsapi_org": "NewsAPI.org",
    "gnews": "GNews",
    "newsdata": "NewsData.io",
}
PROVIDER_QUALITY = {
    "worldnews": 1.0,
    "currents": 0.88,
    "newscatcher": 0.92,
    "newsapi_org": 0.82,
    "gnews": 0.7,
    "newsdata": 0.62,
    "synthetic": 0.6,
}
_PROVIDER_METRICS: dict[str, "ProviderMetricsAccumulator"] = {}
_COUNTRY_PROVIDER_HISTORY: dict[tuple[str, str], "CountryProviderStats"] = {}
_BACKFILL_TASKS: dict[str, asyncio.Task] = {}
_HYDRATED_COUNTRIES: set[str] = set()


@dataclass(slots=True)
class ProviderRuntimeState:
    consecutive_failures: int = 0
    cooldown_until: datetime | None = None
    last_status: str = "idle"
    last_http_status: int | None = None
    last_error: str = ""


@dataclass(slots=True)
class ProviderMetricsAccumulator:
    requests: int = 0
    successes: int = 0
    total_articles: int = 0
    total_latency_ms: float = 0.0
    last_status: str = "idle"


@dataclass(slots=True)
class CountryProviderStats:
    usable_results: int = 0
    total_results: int = 0


@dataclass(slots=True)
class ProviderFetchResult:
    provider: str
    status: str
    message: str
    articles: list[Article] = field(default_factory=list)
    cache_hit: bool = False
    healthy: bool = True
    cooldown_until: datetime | None = None
    last_http_status: int | None = None
    latency_ms: float = 0.0
    languages_used: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NewsPipelineResult:
    feed_articles: list[Article]
    headline_articles: list[Article]
    provider_statuses: list[ProviderStatus]
    pipeline_status: list[PipelineStatus]
    article_cache_hit: bool
    story_clusters: list[StoryCluster]
    observability: ObservabilitySnapshot


async def fetch_country_news(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> NewsPipelineResult:
    """Fetch, normalize, deduplicate, and rank articles from all configured providers."""
    country_code = country_code.upper()
    await _hydrate_country_provider_history(cache, country_code)
    configured_providers = [
        ("worldnews", settings.worldnews_api_key, _fetch_from_worldnews),
        ("currents", settings.currents_api_key, _fetch_from_currents),
        ("newscatcher", settings.newscatcher_api_key, _fetch_from_newscatcher),
        ("newsapi_org", settings.newsapi_org_api_key, _fetch_from_newsapi_org),
        ("gnews", settings.gnews_api_key, _fetch_from_gnews),
        ("newsdata", settings.newsdata_api_key, _fetch_from_newsdata),
    ]

    if not any(api_key for _, api_key, _ in configured_providers):
        fallback = _fallback_articles(country_code=country_code, from_date=from_date)
        return NewsPipelineResult(
            feed_articles=fallback,
            headline_articles=fallback[: settings.summary_article_limit],
            provider_statuses=[
                *[
                    ProviderStatus(
                        provider=provider,
                        status="unconfigured",
                        message=f"{PROVIDER_LABELS.get(provider, provider)} API key is not configured.",
                        healthy=False,
                    )
                    for provider, _, _ in configured_providers
                ],
            ],
            pipeline_status=[
                PipelineStatus(
                    code="synthetic_feed",
                    level="warning",
                    message="No live news providers configured. Showing deterministic placeholder coverage.",
                )
            ],
            article_cache_hit=False,
            story_clusters=[],
            observability=ObservabilitySnapshot(generated_at=datetime.now(timezone.utc)),
        )

    tasks = [
        _load_provider_articles(
            client=client,
            cache=cache,
            settings=settings,
            country_code=country_code,
            from_date=from_date,
            provider=provider,
            api_key=api_key,
            fetcher=fetcher,
        )
        for provider, api_key, fetcher in configured_providers
    ]
    results = await asyncio.gather(*tasks)

    all_articles = [article for result in results for article in result.articles]
    deduped_articles = _deduplicate_articles(all_articles)
    ranked_articles = _rank_articles(
        country_code=country_code,
        settings=settings,
        articles=deduped_articles,
    )
    story_clusters = _cluster_articles(ranked_articles)
    ranked_articles = _attach_cluster_ids(ranked_articles, story_clusters)

    headline_articles = sorted(
        ranked_articles,
        key=lambda article: (article.headline_score, article.feed_score),
        reverse=True,
    )[: settings.summary_article_limit]
    feed_articles = sorted(
        ranked_articles,
        key=lambda article: (article.feed_score, article.headline_score),
        reverse=True,
    )[: settings.news_article_limit]

    provider_statuses = [
        ProviderStatus(
            provider=result.provider,
            status=result.status,
            message=result.message,
            articles_returned=len(result.articles),
            cache_hit=result.cache_hit,
            healthy=result.healthy,
            cooldown_until=result.cooldown_until,
            last_http_status=result.last_http_status,
        )
        for result in results
    ]

    _update_country_provider_history(country_code, feed_articles)
    await _persist_country_provider_history(cache, country_code)

    pipeline_status = _build_pipeline_status(
        provider_results=results,
        deduped_count=len(deduped_articles),
        raw_count=len(all_articles),
        feed_count=len(feed_articles),
        headline_count=len(headline_articles),
    )
    observability = _build_observability_snapshot(results, ranked_articles, story_clusters)
    await cache.set_json(
        "atlas:observability:latest",
        observability.model_dump(mode="json"),
    )

    return NewsPipelineResult(
        feed_articles=feed_articles,
        headline_articles=headline_articles,
        provider_statuses=provider_statuses,
        pipeline_status=pipeline_status,
        article_cache_hit=any(result.cache_hit for result in results),
        story_clusters=story_clusters,
        observability=observability,
    )


async def _load_provider_articles(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
    provider: str,
    api_key: str | None,
    fetcher,
) -> ProviderFetchResult:
    runtime = _PROVIDER_RUNTIME.setdefault(provider, ProviderRuntimeState())
    metrics = _PROVIDER_METRICS.setdefault(provider, ProviderMetricsAccumulator())
    now = datetime.now(timezone.utc)

    if not api_key:
        return ProviderFetchResult(
            provider=provider,
            status="unconfigured",
            message=f"{provider} API key is not configured.",
            healthy=False,
        )

    if runtime.cooldown_until and runtime.cooldown_until > now:
        return ProviderFetchResult(
            provider=provider,
            status="cooldown",
            message=f"{provider} is cooling down after repeated failures.",
            healthy=False,
            cooldown_until=runtime.cooldown_until,
            last_http_status=runtime.last_http_status,
        )

    cache_key = f"atlas:provider:{provider}:{country_code}:{from_date}"
    cached_payload = await cache.get_json(cache_key)
    if cached_payload:
        articles = [Article.model_validate(article) for article in cached_payload.get("articles", [])]
        metrics.requests += 1
        metrics.successes += 1
        metrics.total_articles += len(articles)
        metrics.last_status = cached_payload.get("status", "ok")
        return ProviderFetchResult(
            provider=provider,
            status=cached_payload.get("status", "ok"),
            message=cached_payload.get("message", f"{provider} articles loaded from cache."),
            articles=articles,
            cache_hit=True,
            healthy=cached_payload.get("healthy", True),
            last_http_status=cached_payload.get("last_http_status"),
            latency_ms=0.0,
            languages_used=cached_payload.get("languages_used", []),
        )

    started = perf_counter()
    payload = await fetcher(
        client=client,
        cache=cache,
        settings=settings,
        country_code=country_code,
        from_date=from_date,
    )
    latency_ms = round((perf_counter() - started) * 1000, 2)

    result = ProviderFetchResult(
        provider=provider,
        status=payload["status"],
        message=payload["message"],
        articles=payload["articles"],
        healthy=payload["status"] in {"ok", "empty", "pending"},
        last_http_status=payload.get("last_http_status"),
        latency_ms=latency_ms,
        languages_used=payload.get("languages_used", []),
    )
    metrics.requests += 1
    metrics.total_latency_ms += latency_ms
    metrics.total_articles += len(result.articles)
    metrics.last_status = result.status

    if result.status in {"ok", "empty", "pending"}:
        runtime.consecutive_failures = 0
        runtime.cooldown_until = None
        runtime.last_status = result.status
        runtime.last_http_status = result.last_http_status
        runtime.last_error = ""
        metrics.successes += 1
    else:
        _record_provider_failure(provider=provider, settings=settings, result=result)

    await cache.set_json(
        cache_key,
        {
            "status": result.status,
            "message": result.message,
            "healthy": result.healthy,
            "last_http_status": result.last_http_status,
            "languages_used": result.languages_used,
            "articles": [article.model_dump(mode="json") for article in result.articles],
        },
    )

    # ── Persist timestamped metric to Redis for historical observability ──
    await cache.append_to_list(
        f"atlas:metrics:{provider}",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "latency_ms": latency_ms,
            "articles_returned": len(result.articles),
            "status": result.status,
            "country_code": country_code,
        },
        max_length=500,
    )

    return result


def _record_provider_failure(
    *,
    provider: str,
    settings: Settings,
    result: ProviderFetchResult,
) -> None:
    runtime = _PROVIDER_RUNTIME.setdefault(provider, ProviderRuntimeState())
    runtime.consecutive_failures += 1
    runtime.last_status = result.status
    runtime.last_http_status = result.last_http_status
    runtime.last_error = result.message

    if runtime.consecutive_failures >= settings.provider_failure_threshold:
        runtime.cooldown_until = datetime.now(timezone.utc) + timedelta(
            seconds=settings.provider_cooldown_seconds
        )
        result.cooldown_until = runtime.cooldown_until
        result.healthy = False


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None,
    *,
    label: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: dict | None = None,
) -> dict:
    last_error: dict = {
        "status": "unavailable",
        "message": f"{label} is temporarily unavailable.",
        "last_http_status": None,
        "payload": None,
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json_body,
                timeout=20.0,
            )
            response.raise_for_status()
            return {
                "status": "ok",
                "message": f"{label} returned live coverage.",
                "last_http_status": response.status_code,
                "payload": response.json(),
            }
        except httpx.TimeoutException:
            last_error = {
                "status": "timeout",
                "message": f"{label} timed out while fetching coverage.",
                "last_http_status": None,
                "payload": None,
            }
            logger.warning("%s timeout (attempt %d/%d)", label, attempt + 1, MAX_RETRIES + 1)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            status = "quota_exhausted" if status_code == 429 else "unavailable"
            message = (
                f"{label} quota exhausted."
                if status_code == 429
                else f"{label} returned HTTP {status_code}."
            )
            last_error = {
                "status": status,
                "message": message,
                "last_http_status": status_code,
                "payload": None,
            }
            logger.warning(
                "%s HTTP %s (attempt %d/%d): %s",
                label,
                status_code,
                attempt + 1,
                MAX_RETRIES + 1,
                exc.response.text[:200],
            )
            if status_code < 500 and status_code != 429:
                break
        except httpx.HTTPError as exc:
            last_error = {
                "status": "unavailable",
                "message": f"{label} network error.",
                "last_http_status": None,
                "payload": None,
            }
            logger.warning("%s network error (attempt %d/%d): %s", label, attempt + 1, MAX_RETRIES + 1, exc)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(0.4 * (attempt + 1))

    return last_error


async def _fetch_from_gnews(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> dict:
    iso_a2 = get_iso_a2(country_code)
    country_name = get_country_name(country_code)
    languages = _languages_for_country(country_code, settings.default_language)

    params = {
        "apikey": settings.gnews_api_key,
        "country": iso_a2,
        "lang": languages[0],
        "max": settings.news_article_limit,
        "from": from_date,
        "q": country_name,
    }

    response = await _fetch_with_retry(client, settings.gnews_base_url, params, label="GNews")
    if response["status"] != "ok":
        return {**response, "articles": []}

    items = [
        _build_article(
            provider="gnews",
            source=article.get("source", {}).get("name", "Unknown Source"),
            url=article.get("url", "#"),
            published_at=article.get("publishedAt"),
            title=article.get("title", "Untitled event"),
            snippet=article.get("description") or article.get("content") or "",
            languages_used=languages,
        )
        for article in response["payload"].get("articles", [])[: settings.news_article_limit]
    ]
    items = [article for article in items if article is not None]
    return {
        "status": "ok" if items else "empty",
        "message": "GNews returned live coverage." if items else "GNews returned no country-matched articles.",
        "last_http_status": response["last_http_status"],
        "articles": items,
        "languages_used": languages,
    }


async def _fetch_from_worldnews(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> dict:
    iso_a2 = get_iso_a2(country_code)
    country_name = get_country_name(country_code)
    languages = _languages_for_country(country_code, settings.default_language)

    params = {
        "source-country": iso_a2,
        "language": ",".join(languages),
        "text": country_name,
        "earliest-publish-date": from_date,
        "sort": "publish-time",
        "number": settings.news_article_limit,
    }
    headers = {"x-api-key": settings.worldnews_api_key or ""}

    response = await _fetch_with_retry(
        client, settings.worldnews_base_url, params, label="World News API", headers=headers
    )
    if response["status"] != "ok":
        return {**response, "articles": []}

    items = [
        _build_article(
            provider="worldnews",
            source=_source_name_from_url(article.get("url")) or article.get("source_country", "Unknown Source"),
            url=article.get("url", "#"),
            published_at=article.get("publish_date"),
            title=article.get("title", "Untitled event"),
            snippet=article.get("summary") or article.get("text") or "",
            languages_used=languages,
        )
        for article in response["payload"].get("news", [])[: settings.news_article_limit]
    ]
    items = [article for article in items if article is not None]
    return {
        "status": "ok" if items else "empty",
        "message": "World News API returned live coverage."
        if items
        else "World News API returned no country-matched articles.",
        "last_http_status": response["last_http_status"],
        "articles": items,
        "languages_used": languages,
    }


async def _fetch_from_currents(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> dict:
    country_name = get_country_name(country_code)
    params = {
        "keywords": country_name,
        "language": ",".join(_languages_for_country(country_code, settings.default_language)),
        "start_date": f"{from_date}T00:00:00Z",
        "limit": settings.news_article_limit,
        "country": get_iso_a2(country_code).upper(),
    }
    headers = {"Authorization": settings.currents_api_key or ""}
    response = await _fetch_with_retry(
        client, settings.currents_base_url, params, label="Currents API", headers=headers
    )
    if response["status"] != "ok":
        return {**response, "articles": []}

    items = [
        _build_article(
            provider="currents",
            source=article.get("author") or _source_name_from_url(article.get("url")) or "Unknown Source",
            url=article.get("url", "#"),
            published_at=article.get("published"),
            title=article.get("title", "Untitled event"),
            snippet=article.get("description") or "",
            languages_used=_languages_for_country(country_code, settings.default_language),
        )
        for article in response["payload"].get("news", [])[: settings.news_article_limit]
    ]
    items = [article for article in items if article is not None]
    return {
        "status": "ok" if items else "empty",
        "message": "Currents API returned live coverage." if items else "Currents API returned no country-matched articles.",
        "last_http_status": response["last_http_status"],
        "articles": items,
        "languages_used": _languages_for_country(country_code, settings.default_language),
    }


async def _fetch_from_newscatcher(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> dict:
    country_name = get_country_name(country_code)
    languages = _languages_for_country(country_code, settings.default_language)
    headers = {"x-api-key": settings.newscatcher_api_key or ""}
    catchall_key = f"atlas:catchall:{country_code}:{from_date}"
    cached_result = await cache.get_json(f"{catchall_key}:result")
    if cached_result:
        results_payload = cached_result
    else:
        cached_job = await cache.get_json(f"{catchall_key}:job")
        request_id = cached_job.get("job_id") if cached_job else None

        if request_id:
            results_payload = await _poll_newscatcher_results(
                client=client,
                base_url=settings.newscatcher_base_url,
                headers=headers,
                request_id=request_id,
            )
        else:
            submit_response = await _fetch_with_retry(
                client,
                f"{settings.newscatcher_base_url}/submit",
                None,
                label="NewsCatcher CatchAll",
                method="POST",
                headers=headers,
                json_body={
                    "query": f"Major political, economic, security, infrastructure, or humanitarian developments in {country_name}",
                    "context": f"Focus on developments in {country_name} since {from_date}. Prefer concrete, current events with source citations in {', '.join(languages)} when available.",
                    "start_date": f"{from_date}T00:00:00Z",
                    "limit": settings.news_article_limit,
                },
            )
            if submit_response["status"] != "ok":
                return {**submit_response, "articles": []}

            request_id = (
                submit_response["payload"].get("job_id")
                or submit_response["payload"].get("request_id")
                or submit_response["payload"].get("id")
                or submit_response["payload"].get("requestId")
            )
            if not request_id:
                return {
                    "status": "unavailable",
                    "message": "NewsCatcher CatchAll did not return a request identifier.",
                    "last_http_status": submit_response["last_http_status"],
                    "articles": [],
                }
            await cache.set_json(f"{catchall_key}:job", {"job_id": request_id, "submitted_at": datetime.now(timezone.utc)})
            _ensure_newscatcher_backfill_task(
                task_key=catchall_key,
                client=client,
                cache=cache,
                base_url=settings.newscatcher_base_url,
                headers=headers,
                request_id=request_id,
            )
            return {
                "status": "pending",
                "message": "NewsCatcher CatchAll is enriching results in the background.",
                "last_http_status": None,
                "articles": [],
                "languages_used": languages,
            }

        if results_payload["status"] == "ok":
            await cache.set_json(f"{catchall_key}:result", results_payload)
        elif results_payload["status"] == "timeout":
            _ensure_newscatcher_backfill_task(
                task_key=catchall_key,
                client=client,
                cache=cache,
                base_url=settings.newscatcher_base_url,
                headers=headers,
                request_id=request_id,
            )
            return {
                "status": "pending",
                "message": "NewsCatcher CatchAll is enriching results in the background.",
                "last_http_status": None,
                "articles": [],
                "languages_used": languages,
            }

    if results_payload["status"] != "ok":
        return {**results_payload, "articles": []}

    records = results_payload["payload"].get("records") or results_payload["payload"].get("all_records") or []
    items: list[Article] = []
    for record in records:
        record_title = record.get("record_title") or record.get("title") or "Untitled event"
        record_summary = record.get("ai_summary") or record.get("summary") or ""
        citations = record.get("citations") or []
        if citations:
            for citation in citations:
                article = _build_article(
                    provider="newscatcher",
                    source=_source_name_from_url(citation.get("url")) or citation.get("source", "Unknown Source"),
                    url=citation.get("url", "#"),
                    published_at=citation.get("published_date") or citation.get("publishedAt"),
                    title=citation.get("title") or record_title,
                    snippet=record_summary or citation.get("snippet") or citation.get("description") or "",
                    languages_used=languages,
                )
                if article is not None:
                    items.append(article)
        else:
            article = _build_article(
                provider="newscatcher",
                source=_source_name_from_url(record.get("url")) or "Unknown Source",
                url=record.get("url", "#"),
                published_at=record.get("published_date"),
                title=record_title,
                snippet=record_summary,
                languages_used=languages,
            )
            if article is not None:
                items.append(article)

    items = items[: settings.news_article_limit]
    return {
        "status": "ok" if items else "empty",
        "message": "NewsCatcher CatchAll returned live coverage."
        if items
        else "NewsCatcher CatchAll returned no country-matched articles.",
        "last_http_status": results_payload["last_http_status"],
        "articles": items,
        "languages_used": languages,
    }


async def _poll_newscatcher_results(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    request_id: str,
) -> dict:
    status_url = f"{base_url}/status/{request_id}"
    pull_url = f"{base_url}/pull/{request_id}"

    for _ in range(MAX_CATCHALL_POLLS):
        status_response = await _fetch_with_retry(
            client,
            status_url,
            None,
            label="NewsCatcher CatchAll",
            headers=headers,
        )
        if status_response["status"] != "ok":
            return status_response

        payload = status_response["payload"]
        status = str(payload.get("status", "")).lower()
        if status in {"completed", "success", "done"}:
            pull_response = await _fetch_with_retry(
                client,
                pull_url,
                None,
                label="NewsCatcher CatchAll",
                headers=headers,
            )
            if pull_response["status"] != "ok":
                return pull_response

            pull_payload = pull_response["payload"]
            if isinstance(pull_payload, list):
                return {
                    "status": "ok",
                    "message": "NewsCatcher CatchAll returned live coverage.",
                    "last_http_status": pull_response["last_http_status"],
                    "payload": {"records": pull_payload},
                }
            if isinstance(pull_payload, dict):
                return {
                    "status": "ok",
                    "message": "NewsCatcher CatchAll returned live coverage.",
                    "last_http_status": pull_response["last_http_status"],
                    "payload": pull_payload,
                }
            return {
                "status": "unavailable",
                "message": "NewsCatcher CatchAll returned an unexpected payload shape.",
                "last_http_status": pull_response["last_http_status"],
                "payload": None,
            }

        if status in {"failed", "error"}:
            return {
                "status": "unavailable",
                "message": "NewsCatcher CatchAll job failed.",
                "last_http_status": status_response["last_http_status"],
                "payload": payload,
            }

        await asyncio.sleep(CATCHALL_POLL_DELAY_SECONDS)

    return {
        "status": "timeout",
        "message": "NewsCatcher CatchAll did not complete in time.",
        "last_http_status": None,
        "payload": None,
    }


def _ensure_newscatcher_backfill_task(
    *,
    task_key: str,
    client: httpx.AsyncClient,
    cache: CacheClient,
    base_url: str,
    headers: dict[str, str],
    request_id: str,
) -> None:
    existing = _BACKFILL_TASKS.get(task_key)
    if existing and not existing.done():
        return

    async def runner():
        try:
            payload = await _poll_newscatcher_results(
                client=client,
                base_url=base_url,
                headers=headers,
                request_id=request_id,
            )
            if payload["status"] == "ok":
                await cache.set_json(f"{task_key}:result", payload)
                await cache.set_json(
                    f"{task_key}:job",
                    {"job_id": request_id, "completed": True, "completed_at": datetime.now(timezone.utc)},
                )
        finally:
            _BACKFILL_TASKS.pop(task_key, None)

    _BACKFILL_TASKS[task_key] = asyncio.create_task(runner())


async def _fetch_from_newsapi_org(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> dict:
    country_name = get_country_name(country_code)
    languages = _languages_for_country(country_code, settings.default_language)
    params = {
        "q": f"\"{country_name}\"",
        "searchIn": "title,description,content",
        "language": languages[0],
        "from": from_date,
        "sortBy": "publishedAt",
        "pageSize": settings.news_article_limit,
    }
    headers = {"X-Api-Key": settings.newsapi_org_api_key or ""}

    response = await _fetch_with_retry(
        client, settings.newsapi_org_base_url, params, label="NewsAPI.org", headers=headers
    )
    if response["status"] != "ok":
        return {**response, "articles": []}

    items = [
        _build_article(
            provider="newsapi_org",
            source=article.get("source", {}).get("name", "Unknown Source"),
            url=article.get("url", "#"),
            published_at=article.get("publishedAt"),
            title=article.get("title", "Untitled event"),
            snippet=article.get("description") or article.get("content") or "",
            languages_used=languages,
        )
        for article in response["payload"].get("articles", [])[: settings.news_article_limit]
    ]
    items = [article for article in items if article is not None]
    return {
        "status": "ok" if items else "empty",
        "message": "NewsAPI.org returned live coverage."
        if items
        else "NewsAPI.org returned no country-matched articles.",
        "last_http_status": response["last_http_status"],
        "articles": items,
        "languages_used": languages,
    }


async def _fetch_from_newsdata(
    *,
    client: httpx.AsyncClient,
    cache: CacheClient,
    settings: Settings,
    country_code: str,
    from_date: str,
) -> dict:
    iso_a2 = get_iso_a2(country_code)
    languages = _languages_for_country(country_code, settings.default_language)

    params = {
        "apikey": settings.newsdata_api_key,
        "country": iso_a2,
        "language": languages[0],
        "size": min(settings.news_article_limit, 10),
    }

    response = await _fetch_with_retry(client, settings.newsdata_base_url, params, label="NewsData")
    if response["status"] != "ok":
        return {**response, "articles": []}

    items = [
        _build_article(
            provider="newsdata",
            source=article.get("source_id") or article.get("source_name", "Unknown Source"),
            url=article.get("link", "#"),
            published_at=article.get("pubDate"),
            title=article.get("title", "Untitled event"),
            snippet=article.get("description") or article.get("content") or "",
            languages_used=languages,
        )
        for article in response["payload"].get("results", [])[: settings.news_article_limit]
    ]
    items = [article for article in items if article is not None]
    return {
        "status": "ok" if items else "empty",
        "message": "NewsData.io returned live coverage." if items else "NewsData.io returned no country-matched articles.",
        "last_http_status": response["last_http_status"],
        "articles": items,
        "languages_used": languages,
    }


def _build_article(
    *,
    provider: str,
    source: str,
    url: str,
    published_at: str | None,
    title: str,
    snippet: str,
    languages_used: list[str] | None = None,
) -> Article | None:
    normalized_title = _normalize_text(title)
    normalized_snippet = _normalize_text(snippet)
    canonical_url = _canonicalize_url(url)

    if not normalized_title or not canonical_url:
        return None

    return Article(
        title=normalized_title,
        source=_normalize_text(source) or "Unknown Source",
        provider=provider,
        providers=[provider],
        url=url,
        canonical_url=canonical_url,
        published_at=published_at,
        snippet=normalized_snippet,
        languages_considered=languages_used or [],
    )


def _source_name_from_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    split = urlsplit(raw_url.strip())
    hostname = split.netloc.lower().removeprefix("www.")
    return hostname or None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = unescape(value)
    cleaned = HTML_TAG_PATTERN.sub(" ", cleaned)
    cleaned = BOILERPLATE_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = WHITESPACE_PATTERN.sub(" ", cleaned)
    return cleaned.strip(" -|")


def _canonicalize_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    split = urlsplit(raw_url.strip())
    if not split.scheme or not split.netloc:
        return None
    query = urlencode(
        [(key, value) for key, value in parse_qsl(split.query, keep_blank_values=False) if key.lower() not in TRACKING_PARAMS]
    )
    path = split.path.rstrip("/") or "/"
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, query, ""))


def _deduplicate_articles(articles: list[Article]) -> list[Article]:
    deduped: list[Article] = []

    for candidate in articles:
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(deduped)
                if _articles_match(existing, candidate)
            ),
            None,
        )
        if duplicate_index is None:
            deduped.append(candidate)
            continue

        deduped[duplicate_index] = _merge_articles(deduped[duplicate_index], candidate)

    return deduped


def _articles_match(left: Article, right: Article) -> bool:
    if left.canonical_url and right.canonical_url and left.canonical_url == right.canonical_url:
        return True
    title_similarity = SequenceMatcher(None, _normalize_key(left.title), _normalize_key(right.title)).ratio()
    return title_similarity >= 0.9


def _merge_articles(left: Article, right: Article) -> Article:
    left_value = _article_completeness(left)
    right_value = _article_completeness(right)
    primary, secondary = (left, right) if left_value >= right_value else (right, left)

    return primary.model_copy(
        update={
            "providers": sorted(set(primary.providers + secondary.providers)),
            "matched_terms": sorted(set(primary.matched_terms + secondary.matched_terms)),
            "snippet": primary.snippet if len(primary.snippet) >= len(secondary.snippet) else secondary.snippet,
        }
    )


def _article_completeness(article: Article) -> tuple[int, int, int]:
    published = int(article.published_at.timestamp()) if article.published_at else 0
    return (len(article.snippet), len(article.providers), published)


def _rank_articles(
    *,
    country_code: str,
    settings: Settings,
    articles: list[Article],
) -> list[Article]:
    preferred_sources = {
        source.strip().lower() for source in settings.preferred_news_sources.split(",") if source.strip()
    }
    penalty_terms = {
        term.strip().lower() for term in settings.clickbait_source_penalty_terms.split(",") if term.strip()
    }
    scored: list[Article] = []
    for article in articles:
        matched_terms, relevance_score = _score_country_relevance(country_code, article)
        category = _detect_category(article)
        evidence_points = _extract_evidence(article)
        entities = _extract_entities(article)
        provider_performance_score = _provider_country_score(country_code, article.provider)
        source_trust_score = _score_source_quality(article, preferred_sources, penalty_terms)
        quality_score = round((source_trust_score * 0.7) + (provider_performance_score * 0.3), 4)
        freshness_score = _score_freshness(article)
        snippet_score = _score_snippet(article.snippet)
        evidence_score = min(1.0, len(evidence_points) / 3)
        entity_score = min(1.0, len(entities) / 4)
        headline_score = round(
            (relevance_score * 0.42)
            + (quality_score * 0.22)
            + (freshness_score * 0.2)
            + (snippet_score * 0.1)
            + (evidence_score * 0.04)
            + (entity_score * 0.02),
            4,
        )
        feed_score = round(
            (relevance_score * 0.36)
            + (quality_score * 0.18)
            + (freshness_score * 0.28)
            + (snippet_score * 0.1)
            + (evidence_score * 0.05)
            + (entity_score * 0.03),
            4,
        )
        if article.source == SUMMARY_FALLBACK_SOURCE or relevance_score >= settings.news_min_relevance_score:
            scored.append(
                article.model_copy(
                    update={
                        "matched_terms": matched_terms,
                        "relevance_score": round(relevance_score, 4),
                        "quality_score": round(quality_score, 4),
                        "freshness_score": round(freshness_score, 4),
                        "headline_score": headline_score,
                        "feed_score": feed_score,
                        "is_preferred_source": _normalize_key(article.source) in preferred_sources,
                        "confidence": _confidence_band(relevance_score, quality_score, evidence_score),
                        "category": category,
                        "evidence_points": evidence_points,
                        "entities": entities,
                        "source_trust_score": round(source_trust_score, 4),
                        "provider_performance_score": round(provider_performance_score, 4),
                    }
                )
            )
    return scored


def _detect_category(article: Article) -> str:
    haystack = _normalize_key(f"{article.title} {article.snippet}")
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "general"


def _extract_evidence(article: Article) -> list[str]:
    text = _normalize_text(f"{article.title}. {article.snippet}")
    evidence = []
    for sentence in SENTENCE_SPLIT_PATTERN.split(text):
        trimmed = sentence.strip()
        if not trimmed:
            continue
        if DATE_PATTERN.search(trimmed) or NUMBER_PATTERN.search(trimmed):
            evidence.append(trimmed[:140])
        if len(evidence) == 3:
            break
    if not evidence and article.snippet:
        evidence.append(article.snippet[:140])
    return evidence


def _extract_entities(article: Article) -> list[str]:
    entities = []
    for fragment in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", article.title):
        if fragment not in entities:
            entities.append(fragment)
    return entities[:5]


def _confidence_band(relevance_score: float, quality_score: float, evidence_score: float) -> str:
    combined = (relevance_score * 0.5) + (quality_score * 0.3) + (evidence_score * 0.2)
    if combined >= 0.78:
        return "high"
    if combined >= 0.52:
        return "medium"
    return "low"


def _score_country_relevance(country_code: str, article: Article) -> tuple[list[str], float]:
    country_name = get_country_name(country_code)
    text_title = f" {_normalize_key(article.title)} "
    text_snippet = f" {_normalize_key(article.snippet)} "
    signals = _country_signals(country_code, country_name)
    matches: list[str] = []
    score = 0.0

    for term in signals["aliases"]:
        if f" {term} " in text_title:
            matches.append(term)
            score += 0.55
        elif f" {term} " in text_snippet:
            matches.append(term)
            score += 0.35

    for term in signals["demonyms"]:
        if f" {term} " in text_title:
            matches.append(term)
            score += 0.3
        elif f" {term} " in text_snippet:
            matches.append(term)
            score += 0.2

    for term in signals["places"] + signals["entities"]:
        if f" {term} " in text_title:
            matches.append(term)
            score += 0.22
        elif f" {term} " in text_snippet:
            matches.append(term)
            score += 0.14

    has_generic_political_term = any(f" {term} " in text_title or f" {term} " in text_snippet for term in GENERIC_POLITICAL_TERMS)
    if matches and has_generic_political_term:
        score += 0.12

    if article.provider == "worldnews":
        score += 0.1
    elif article.provider == "newscatcher":
        score += 0.08
    elif article.provider == "newsapi_org":
        score += 0.07
    elif article.provider == "gnews":
        score += 0.06
    elif article.provider == "newsdata":
        score += 0.05

    return sorted(set(matches)), min(score, 1.0)


def _country_signals(country_code: str, country_name: str) -> dict[str, list[str]]:
    """Build relevance signals from the enriched CountryInfo knowledge base."""
    normalized_name = _normalize_key(country_name).replace("-", " ")
    aliases = {normalized_name}
    words = [word for word in normalized_name.split() if len(word) > 3]
    aliases.update(words)
    safe_short_aliases = {"uae", "prc", "rok", "dprk", "uk", "u.k.", "u.s."}

    def clean_terms(terms: tuple[str, ...] | list[str]) -> set[str]:
        cleaned = {_normalize_key(term).replace("-", " ") for term in terms}
        return {term for term in cleaned if len(term) >= 2 or term in safe_short_aliases}

    info = get_country_info(country_code)
    if info:
        aliases.update(clean_terms(info.aliases))
        if info.capital:
            aliases.add(_normalize_key(info.capital))
        demonyms = clean_terms(info.demonyms)
        places = clean_terms(info.major_cities + info.regions)
        entities = clean_terms(
            info.key_entities + info.key_ministries + info.leader_titles
        )
    else:
        demonyms = set()
        places = set()
        entities = set()

    return {
        "aliases": sorted(aliases),
        "demonyms": sorted(demonyms),
        "places": sorted(places),
        "entities": sorted(entities),
    }


def _score_source_quality(article: Article, preferred_sources: set[str], penalty_terms: set[str]) -> float:
    """Score source quality using the source reputation table + provider quality."""
    source_key = _normalize_key(article.source)
    provider_score = PROVIDER_QUALITY.get(article.provider, 0.6)
    penalty = 0.0
    if any(term in source_key for term in penalty_terms):
        penalty = 0.12

    # Use the source reputation service for domain-level trust
    domain = _source_domain_from_article(article)
    reputation_score = get_source_trust_sync(domain) if domain else 0.58

    # Blend reputation with provider quality (reputation weighted heavier)
    blended = (reputation_score * 0.65) + (provider_score * 0.35)

    if source_key in preferred_sources:
        blended = max(blended, 0.92)
    elif any(pattern in source_key for pattern in preferred_sources):
        blended = max(blended, 0.85)

    return max(0.0, min(1.0, blended - penalty))


def _source_domain_from_article(article: Article) -> str:
    """Extract the domain from an article URL for reputation lookups."""
    try:
        parts = urlsplit(article.url)
        domain = parts.hostname or ""
        return domain.lower().removeprefix("www.")
    except Exception:
        return ""


def _score_freshness(article: Article) -> float:
    if not article.published_at:
        return 0.35
    now = datetime.now(timezone.utc)
    published_at = article.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max((now - published_at).total_seconds() / 3600, 0)
    category = article.category or _detect_category(article)
    decay_window = CATEGORY_DECAY_HOURS.get(category, CATEGORY_DECAY_HOURS["general"])
    return max(0.0, min(1.0, 1 - (age_hours / decay_window)))


def _score_snippet(snippet: str) -> float:
    length = len(snippet)
    if length == 0:
        return 0.0
    if 80 <= length <= 280:
        return 1.0
    if 40 <= length < 80 or 280 < length <= 420:
        return 0.72
    return 0.45


def _normalize_key(value: str) -> str:
    return NON_ALNUM_PATTERN.sub(" ", value.lower()).strip()


def _languages_for_country(country_code: str, default_language: str) -> list[str]:
    languages = LOCAL_LANGUAGE_HINTS.get(country_code.upper(), [default_language])
    if default_language not in languages:
        languages.append(default_language)
    return languages[:2]


def _provider_country_score(country_code: str, provider: str) -> float:
    stats = _COUNTRY_PROVIDER_HISTORY.get((country_code, provider))
    if not stats or stats.total_results == 0:
        return PROVIDER_QUALITY.get(provider, 0.6)
    observed = stats.usable_results / stats.total_results
    return round((PROVIDER_QUALITY.get(provider, 0.6) * 0.6) + (observed * 0.4), 4)


def _update_country_provider_history(country_code: str, articles: list[Article]) -> None:
    providers = {article.provider for article in articles}
    for provider in PROVIDER_LABELS:
        stats = _COUNTRY_PROVIDER_HISTORY.setdefault((country_code, provider), CountryProviderStats())
        stats.total_results += 1
        if provider in providers:
            stats.usable_results += 1


def _title_ngrams(title: str, n: int = 2) -> set[str]:
    """Generate word-level n-grams from a normalized title for Jaccard similarity."""
    words = _normalize_key(title).split()
    if len(words) < n:
        return set(words)
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _cluster_articles(articles: list[Article]) -> list[StoryCluster]:
    """Cluster articles using Jaccard n-gram similarity with SequenceMatcher fallback."""
    clusters: list[tuple[set[str], list[Article]]] = []
    for article in articles:
        article_ngrams = _title_ngrams(article.title)
        matched_cluster = None
        best_score = 0.0
        for cluster_ngrams, cluster_articles in clusters:
            # Primary: Jaccard n-gram similarity
            jaccard = _jaccard_similarity(cluster_ngrams, article_ngrams)
            if jaccard >= 0.35:
                # Secondary: SequenceMatcher for confirmation at lower Jaccard scores
                if jaccard >= 0.55 or SequenceMatcher(
                    None,
                    _normalize_key(cluster_articles[0].title),
                    _normalize_key(article.title),
                ).ratio() >= 0.58:
                    if jaccard > best_score:
                        best_score = jaccard
                        matched_cluster = (cluster_ngrams, cluster_articles)
        if matched_cluster is None:
            clusters.append((article_ngrams, [article]))
        else:
            matched_cluster[0].update(article_ngrams)
            matched_cluster[1].append(article)

    story_clusters = []
    for index, (_, cluster) in enumerate(
        sorted(clusters, key=lambda c: len(c[1]), reverse=True), start=1
    ):
        representative = max(cluster, key=lambda article: article.headline_score)
        story_clusters.append(
            StoryCluster(
                cluster_id=f"cluster-{index}",
                label=representative.category,
                article_count=len(cluster),
                representative_title=representative.title,
                providers=sorted({provider for article in cluster for provider in article.providers}),
                evidence_points=representative.evidence_points[:3],
            )
        )
    return story_clusters


def _attach_cluster_ids(articles: list[Article], clusters: list[StoryCluster]) -> list[Article]:
    """Attach cluster IDs using Jaccard n-gram similarity."""
    cluster_ngrams = [
        (_title_ngrams(cluster.representative_title), cluster.cluster_id)
        for cluster in clusters
    ]
    attached = []
    for article in articles:
        article_ngrams = _title_ngrams(article.title)
        best_id = None
        best_score = 0.0
        for c_ngrams, c_id in cluster_ngrams:
            score = _jaccard_similarity(c_ngrams, article_ngrams)
            if score > best_score and score >= 0.30:
                best_score = score
                best_id = c_id
        attached.append(article.model_copy(update={"cluster_id": best_id}))
    return attached


def _build_observability_snapshot(
    results: list[ProviderFetchResult],
    ranked_articles: list[Article],
    story_clusters: list[StoryCluster],
) -> ObservabilitySnapshot:
    provider_metrics = []
    for provider, metric in _PROVIDER_METRICS.items():
        provider_metrics.append(
            ProviderMetric(
                provider=provider,
                success_rate=round(metric.successes / metric.requests, 4) if metric.requests else 0.0,
                average_articles=round(metric.total_articles / metric.requests, 2) if metric.requests else 0.0,
                average_latency_ms=round(metric.total_latency_ms / metric.requests, 2) if metric.requests else 0.0,
                last_status=metric.last_status,
            )
        )
    return ObservabilitySnapshot(
        generated_at=datetime.now(timezone.utc),
        provider_metrics=sorted(provider_metrics, key=lambda item: item.provider),
        ranked_article_count=len(ranked_articles),
        cluster_count=len(story_clusters),
    )


def get_global_observability_snapshot() -> ObservabilitySnapshot:
    return _build_observability_snapshot([], [], [])


async def get_historical_provider_metrics(
    cache: CacheClient, provider: str, count: int = 100
) -> list[HistoricalMetric]:
    """Retrieve persisted historical metrics for a provider from Redis."""
    raw = await cache.get_list(f"atlas:metrics:{provider}", count)
    return [
        HistoricalMetric(
            timestamp=datetime.fromisoformat(entry["timestamp"]),
            provider=entry.get("provider", provider),
            latency_ms=entry.get("latency_ms", 0.0),
            articles_returned=entry.get("articles_returned", 0),
            status=entry.get("status", "unknown"),
            country_code=entry.get("country_code", ""),
        )
        for entry in raw
        if isinstance(entry, dict) and "timestamp" in entry
    ]


async def get_enriched_observability_snapshot(cache: CacheClient) -> ObservabilitySnapshot:
    """Build a full observability snapshot with historical data from Redis."""
    base = _build_observability_snapshot([], [], [])

    # Gather historical metrics from all known providers
    all_historical: list[HistoricalMetric] = []
    for provider in PROVIDER_LABELS:
        metrics = await get_historical_provider_metrics(cache, provider, count=50)
        all_historical.extend(metrics)

    # Build country quality snapshots from provider history
    country_quality: list[CountryQualitySnapshot] = []
    country_codes_seen: set[str] = set()
    for (code, _), stats in _COUNTRY_PROVIDER_HISTORY.items():
        if code not in country_codes_seen and stats.total_results > 0:
            country_codes_seen.add(code)
            country_quality.append(
                CountryQualitySnapshot(
                    country_code=code,
                    country_name=get_country_name(code),
                    usable_yield=round(stats.usable_results / max(stats.total_results, 1), 4),
                    provider_count=sum(
                        1 for (c, _), s in _COUNTRY_PROVIDER_HISTORY.items()
                        if c == code and s.usable_results > 0
                    ),
                    last_updated=datetime.now(timezone.utc),
                )
            )

    # Stale cache warnings
    stale_warnings: list[str] = []
    for provider, runtime in _PROVIDER_RUNTIME.items():
        if runtime.cooldown_until and runtime.cooldown_until > datetime.now(timezone.utc):
            stale_warnings.append(
                f"{PROVIDER_LABELS.get(provider, provider)} is in cooldown until "
                f"{runtime.cooldown_until.strftime('%H:%M:%S UTC')}"
            )

    base.historical_metrics = sorted(all_historical, key=lambda m: m.timestamp, reverse=True)
    base.country_quality = sorted(country_quality, key=lambda c: c.usable_yield, reverse=True)
    base.stale_cache_warnings = stale_warnings
    return base


async def _hydrate_country_provider_history(cache: CacheClient, country_code: str) -> None:
    if country_code in _HYDRATED_COUNTRIES:
        return
    payload = await cache.get_json(f"atlas:provider-history:{country_code}")
    if payload:
        for provider, stats in payload.items():
            _COUNTRY_PROVIDER_HISTORY[(country_code, provider)] = CountryProviderStats(
                usable_results=stats.get("usable_results", 0),
                total_results=stats.get("total_results", 0),
            )
    _HYDRATED_COUNTRIES.add(country_code)


async def _persist_country_provider_history(cache: CacheClient, country_code: str) -> None:
    payload = {
        provider: {
            "usable_results": stats.usable_results,
            "total_results": stats.total_results,
        }
        for (code, provider), stats in _COUNTRY_PROVIDER_HISTORY.items()
        if code == country_code
    }
    if payload:
        await cache.set_json(f"atlas:provider-history:{country_code}", payload)


def _build_pipeline_status(
    *,
    provider_results: list[ProviderFetchResult],
    deduped_count: int,
    raw_count: int,
    feed_count: int,
    headline_count: int,
) -> list[PipelineStatus]:
    statuses: list[PipelineStatus] = []

    if raw_count and deduped_count < raw_count:
        statuses.append(
            PipelineStatus(
                code="deduplicated_feed",
                level="info",
                message=f"Merged {raw_count - deduped_count} duplicate articles across providers.",
            )
        )

    if any(result.status == "quota_exhausted" for result in provider_results):
        statuses.append(
            PipelineStatus(
                code="news_provider_unavailable",
                level="warning",
                message="One or more news providers are currently unavailable.",
            )
        )

    if all(result.status in {"quota_exhausted", "unavailable", "timeout", "cooldown", "unconfigured"} for result in provider_results):
        statuses.append(
            PipelineStatus(
                code="raw_news_unavailable",
                level="error",
                message="Live news providers are unavailable for this request.",
            )
        )

    if feed_count and headline_count:
        statuses.append(
            PipelineStatus(
                code="ranked_selection_ready",
                level="info",
                message=f"Selected {headline_count} headline articles from a ranked feed of {feed_count}.",
            )
        )

    return statuses


def _fallback_articles(*, country_code: str, from_date: str) -> list[Article]:
    """Generate deterministic placeholder content when no API keys are available."""
    country_name = get_country_name(country_code)
    return [
        Article(
            title=f"{country_name} — Intelligence feed active",
            source=SUMMARY_FALLBACK_SOURCE,
            provider="synthetic",
            providers=["synthetic"],
            url="https://example.com/atlas-intelligence",
            canonical_url="https://example.com/atlas-intelligence",
            snippet=(
                f"Connect GNews or NewsData.io credentials to receive live intelligence for {country_name}. "
                f"Current historical sweep start date: {from_date}."
            ),
            relevance_score=1.0,
            quality_score=0.8,
            freshness_score=1.0,
            headline_score=0.9,
            feed_score=0.9,
        ),
        Article(
            title=f"{country_name} — Regional monitoring initialized",
            source=SUMMARY_FALLBACK_SOURCE,
            provider="synthetic",
            providers=["synthetic"],
            url="https://example.com/atlas-intelligence",
            canonical_url="https://example.com/atlas-intelligence",
            snippet=(
                f"Atlas.Intelligence is monitoring the {country_name} region. "
                "Real article feeds will replace these synthetic payloads once API keys are configured."
            ),
            relevance_score=1.0,
            quality_score=0.8,
            freshness_score=1.0,
            headline_score=0.88,
            feed_score=0.88,
        ),
        Article(
            title=f"Geopolitical context: {country_name}",
            source=SUMMARY_FALLBACK_SOURCE,
            provider="synthetic",
            providers=["synthetic"],
            url="https://example.com/atlas-intelligence",
            canonical_url="https://example.com/atlas-intelligence",
            snippet=(
                f"This placeholder simulates the intelligence pipeline for {country_name}. "
                "Sentiment analysis, situation reports, and main event extraction will activate with live data."
            ),
            relevance_score=1.0,
            quality_score=0.8,
            freshness_score=1.0,
            headline_score=0.86,
            feed_score=0.86,
        ),
    ]
