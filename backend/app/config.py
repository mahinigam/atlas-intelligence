from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Atlas.Intelligence API"
    api_prefix: str = "/api/v1"
    debug: bool = False

    postgres_dsn: str = Field(default="postgresql+asyncpg://atlas:atlas@localhost:5432/atlas")
    redis_url: str = Field(default="redis://localhost:6379/0")

    gemini_api_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    )
    gemini_api_key: str | None = None

    worldnews_api_key: str | None = None
    worldnews_base_url: str = "https://api.worldnewsapi.com/search-news"
    currents_api_key: str | None = None
    currents_base_url: str = "https://api.currentsapi.services/v1/search"
    newscatcher_api_key: str | None = None
    newscatcher_base_url: str = "https://catchall.newscatcherapi.com/catchAll"
    newsapi_org_api_key: str | None = None
    newsapi_org_base_url: str = "https://newsapi.org/v2/everything"
    gnews_api_key: str | None = None
    gnews_base_url: str = "https://gnews.io/api/v4/search"
    newsdata_api_key: str | None = None
    newsdata_base_url: str = "https://newsdata.io/api/1/latest"

    default_language: str = "en"
    cache_ttl_seconds: int = 900
    news_article_limit: int = 12
    summary_article_limit: int = 5
    news_min_relevance_score: float = 0.35
    provider_failure_threshold: int = 3
    provider_cooldown_seconds: int = 600
    catchall_async_poll_ttl_seconds: int = 3600
    preferred_news_sources: str = (
        "reuters,associated press,ap news,bloomberg,financial times,bbc,al jazeera,"
        "the guardian,washington post,wall street journal,nikkei"
    )
    clickbait_source_penalty_terms: str = "opinion,blog,rumor,viral,celebrity,tabloid"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
