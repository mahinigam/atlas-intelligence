"""Atlas.Intelligence — FastAPI backend for geopolitical intelligence."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.cache import CacheClient
from app.config import Settings, get_settings
from app.country_metadata import COUNTRIES, get_country_name
from app.dependencies import get_cache, get_http_client
from app.schemas import IntelligenceResponse
from app.services.news import fetch_country_news
from app.services.summarizer import summarize_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("atlas")


@asynccontextmanager
async def lifespan(_: FastAPI):
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
    from_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    cache: CacheClient = Depends(get_cache),
    client: httpx.AsyncClient = Depends(get_http_client),
    app_settings: Settings = Depends(get_settings),
) -> IntelligenceResponse:
    country_code = country_code.upper()
    country_name = get_country_name(country_code)
    cache_key = f"atlas:intelligence:{country_code}:{from_date}"

    logger.info("Intelligence request: %s (%s) from %s", country_code, country_name, from_date)

    cached_payload = await cache.get_json(cache_key)
    if cached_payload:
        logger.info("Cache HIT for %s", cache_key)
        return IntelligenceResponse.model_validate(cached_payload)

    logger.info("Cache MISS for %s — fetching live data", cache_key)

    articles = list(
        await fetch_country_news(
            client=client,
            settings=app_settings,
            country_code=country_code,
            from_date=from_date,
        )
    )

    summary = await summarize_articles(
        client=client,
        settings=app_settings,
        country_name=country_name,
        from_date=from_date,
        articles=articles,
    )

    response = IntelligenceResponse(
        country_code=country_code,
        country_name=country_name,
        main_event=summary.main_event,
        regional_sentiment=summary.regional_sentiment,
        situation_report=summary.situation_report,
        from_date=from_date,
        updated_at=datetime.now(timezone.utc),
        articles=articles,
    )
    await cache.set_json(cache_key, response.model_dump(mode="json"))
    return response
