import json
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.cache import CacheClient
from app.config import Settings, get_settings
from app.country_metadata import COUNTRIES, get_country_name
from app.dependencies import get_cache, get_http_client
from app.schemas import CacheStatus, GeminiSummary, HistoricalMetric, IntelligenceResponse, SummaryStatus
from app.services.news import fetch_country_news, get_enriched_observability_snapshot, get_historical_provider_metrics
from app.services.summarizer import AIUnavailableError, summarize_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("atlas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=40.0) as client:
        app.state.client = client
        logger.info("Atlas.Intelligence backend starting — %d countries loaded", len(COUNTRIES))
        yield
    logger.info("Atlas.Intelligence backend shutting down")


settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get(f"{settings.api_prefix}/observability")
async def observability(
    cache: CacheClient = Depends(get_cache),
):
    """Return enriched observability snapshot with historical metrics and country quality."""
    return await get_enriched_observability_snapshot(cache)


@app.get(f"{settings.api_prefix}/observability/providers/{{provider}}")
async def observability_provider(
    provider: str,
    count: int = Query(default=100, ge=1, le=500),
    cache: CacheClient = Depends(get_cache),
):
    """Return historical metrics for a specific provider."""
    metrics = await get_historical_provider_metrics(cache, provider, count=count)
    return {
        "provider": provider,
        "count": len(metrics),
        "metrics": [m.model_dump(mode="json") for m in metrics],
    }


@app.get(f"{settings.api_prefix}/countries")
async def list_countries() -> list[dict[str, str]]:
    """Return all supported countries for the frontend country list."""
    return [
        {"iso_a3": code, "name": info.name, "iso_a2": info.iso_a2}
        for code, info in sorted(COUNTRIES.items(), key=lambda x: x[1].name)
    ]


@app.get(f"{settings.api_prefix}/intelligence", response_model=IntelligenceResponse)
async def get_intelligence(
    country_code: str = Query(..., min_length=2, max_length=3),
    from_date: str = Query(default_factory=_default_from_date, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    cache: CacheClient = Depends(get_cache),
    client: httpx.AsyncClient = Depends(get_http_client),
    app_settings: Settings = Depends(get_settings),
) -> IntelligenceResponse:
    country_code = country_code.upper()
    country_name = get_country_name(country_code)
    logger.info("Intelligence request: %s (%s) from %s", country_code, country_name, from_date)
    news_pipeline = await fetch_country_news(
        client=client,
        cache=cache,
        settings=app_settings,
        country_code=country_code,
        from_date=from_date,
    )

    summary_cache_key = _summary_cache_key(
        country_code=country_code,
        from_date=from_date,
        headline_articles=news_pipeline.headline_articles,
    )
    cached_summary_payload = await cache.get_json(summary_cache_key)
    if cached_summary_payload:
        summary = GeminiSummary.model_validate(cached_summary_payload["summary"])
        summary_status = SummaryStatus.model_validate(cached_summary_payload["status"]).model_copy(
            update={"cache_hit": True}
        )
        logger.info("Summary cache HIT for %s", summary_cache_key)
    else:
        try:
            summary_result = await summarize_articles(
                client=client,
                settings=app_settings,
                country_name=country_name,
                from_date=from_date,
                articles=news_pipeline.headline_articles,
            )
        except AIUnavailableError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        summary = summary_result.summary
        summary_status = summary_result.status
        await cache.set_json(
            summary_cache_key,
            {
                "summary": summary.model_dump(mode="json"),
                "status": summary_status.model_dump(mode="json"),
            },
        )

    response = IntelligenceResponse(
        country_code=country_code,
        country_name=country_name,
        main_event=summary.main_event,
        regional_sentiment=summary.regional_sentiment,
        situation_report=summary.situation_report,
        from_date=from_date,
        updated_at=datetime.now(timezone.utc),
        articles=news_pipeline.feed_articles,
        headline_articles=news_pipeline.headline_articles,
        provider_statuses=news_pipeline.provider_statuses,
        summary_status=summary_status,
        pipeline_status=news_pipeline.pipeline_status,
        cache=CacheStatus(
            article_cache_hit=news_pipeline.article_cache_hit,
            summary_cache_hit=summary_status.cache_hit,
        ),
        story_clusters=news_pipeline.story_clusters,
        observability=news_pipeline.observability,
    )
    return response


@app.get(f"{settings.api_prefix}/intelligence/stream")
async def stream_intelligence(
    country_code: str = Query(..., min_length=2, max_length=3),
    from_date: str = Query(default_factory=_default_from_date, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    client: httpx.AsyncClient = Depends(get_http_client),
    app_settings: Settings = Depends(get_settings),
):
    country_code = country_code.upper()
    country_name = get_country_name(country_code)

    async def event_generator():
        news_pipeline = await fetch_country_news(
            client=client,
            cache=CacheClient(redis_client=None, ttl_seconds=app_settings.cache_ttl_seconds),
            settings=app_settings,
            country_code=country_code,
            from_date=from_date,
        )
        status_json = json.dumps([status.model_dump(mode="json") for status in news_pipeline.provider_statuses])
        yield f"event: provider_status\ndata: {status_json}\n\n"

        articles_json = json.dumps([a.model_dump(mode="json") for a in news_pipeline.feed_articles])
        yield f"event: news\ndata: {articles_json}\n\n"

        try:
            summary_result = await summarize_articles(
                client=client,
                settings=app_settings,
                country_name=country_name,
                from_date=from_date,
                articles=list(news_pipeline.headline_articles),
            )
        except AIUnavailableError as exc:
            error_payload = {"detail": str(exc), "status_code": exc.status_code}
            yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
            yield "event: end\ndata: {}\n\n"
            return

        summary = summary_result.summary
        summary_status = summary_result.status
        final_payload = {
            **summary.model_dump(mode="json"),
            "summary_status": summary_status.model_dump(mode="json"),
            "headline_articles": [a.model_dump(mode="json") for a in news_pipeline.headline_articles],
            "pipeline_status": [
                status.model_dump(mode="json")
                for status in news_pipeline.pipeline_status
            ],
            "cache": {
                "article_cache_hit": news_pipeline.article_cache_hit,
                "summary_cache_hit": False,
            },
            "story_clusters": [cluster.model_dump(mode="json") for cluster in news_pipeline.story_clusters],
            "observability": news_pipeline.observability.model_dump(mode="json"),
        }
        yield f"event: final\ndata: {json.dumps(final_payload)}\n\n"

        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _summary_cache_key(*, country_code: str, from_date: str, headline_articles: list) -> str:
    digest = hashlib.sha256(
        json.dumps(
            [
                {
                    "title": article.title,
                    "canonical_url": article.canonical_url,
                    "snippet": article.snippet,
                }
                for article in headline_articles
            ],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"atlas:summary:{country_code}:{from_date}:{digest}"


def _default_from_date() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
