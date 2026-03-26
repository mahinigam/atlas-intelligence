from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Atlas.Intelligence API"
    api_prefix: str = "/api/v1"
    debug: bool = False

    postgres_dsn: str = Field(default="postgresql+asyncpg://atlas:atlas@localhost:5432/atlas")
    redis_url: str = Field(default="redis://localhost:6379/0")

    gemini_api_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    )
    gemini_api_key: str | None = None

    gnews_api_key: str | None = None
    gnews_base_url: str = "https://gnews.io/api/v4/search"
    newsdata_api_key: str | None = None
    newsdata_base_url: str = "https://newsdata.io/api/1/latest"

    default_language: str = "en"
    cache_ttl_seconds: int = 900
    news_article_limit: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
