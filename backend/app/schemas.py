from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class Article(BaseModel):
    title: str
    source: str
    provider: str = "unknown"
    providers: list[str] = Field(default_factory=list)
    url: str
    canonical_url: str | None = None
    published_at: datetime | None = None
    snippet: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.0, ge=0.0)
    quality_score: float = Field(default=0.0, ge=0.0)
    freshness_score: float = Field(default=0.0, ge=0.0)
    headline_score: float = Field(default=0.0, ge=0.0)
    feed_score: float = Field(default=0.0, ge=0.0)
    is_preferred_source: bool = False
    confidence: str = "medium"
    category: str = "general"
    cluster_id: str | None = None
    evidence_points: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    source_trust_score: float = Field(default=0.0, ge=0.0)
    provider_performance_score: float = Field(default=0.0, ge=0.0)
    languages_considered: list[str] = Field(default_factory=list)

    @field_validator("published_at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime | None:
        if not v or isinstance(v, datetime):
            return v
        if isinstance(v, str):
            v = v.strip()
            try:
                # Handle formats like '2026-03-27 02:11:23 +0000'
                if " " in v and ("+" in v or "-" in v):
                    # Replace space before offset with T or just remove it if it's the offset space
                    # Example: '2026-03-27 02:11:23 +0000' -> '2026-03-27T02:11:23+0000'
                    parts = v.rsplit(" ", 1)
                    if len(parts) == 2 and (parts[1].startswith("+") or parts[1].startswith("-")):
                        v = f"{parts[0].replace(' ', 'T')}{parts[1]}"
                
                # Try fromisoformat first (very fast on modern Python)
                return datetime.fromisoformat(v.replace(" ", "T") if "T" not in v else v)
            except (ValueError, TypeError):
                # If everything fails, return None rather than crashing the whole request
                return None
        return None


class ProviderStatus(BaseModel):
    provider: str
    status: str
    message: str
    articles_returned: int = 0
    cache_hit: bool = False
    healthy: bool = True
    cooldown_until: datetime | None = None
    last_http_status: int | None = None


class SummaryStatus(BaseModel):
    status: str
    message: str
    used_ai: bool = False
    cache_hit: bool = False
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    thoughts_tokens: int | None = None


class PipelineStatus(BaseModel):
    code: str
    level: str
    message: str


class CacheStatus(BaseModel):
    article_cache_hit: bool = False
    summary_cache_hit: bool = False


class StoryCluster(BaseModel):
    cluster_id: str
    label: str
    article_count: int
    representative_title: str
    providers: list[str] = Field(default_factory=list)
    evidence_points: list[str] = Field(default_factory=list)


class ProviderMetric(BaseModel):
    provider: str
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_articles: float = Field(default=0.0, ge=0.0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)
    last_status: str = "unknown"


# ── Historical Metrics (persisted to Redis time-series) ───────────────────

class HistoricalMetric(BaseModel):
    """A single timestamped metric record for a provider."""
    timestamp: datetime
    provider: str
    latency_ms: float = 0.0
    articles_returned: int = 0
    status: str = "unknown"
    country_code: str = ""


class CountryQualitySnapshot(BaseModel):
    """Aggregated quality signal for a country's news coverage."""
    country_code: str
    country_name: str = ""
    avg_relevance: float = 0.0
    avg_freshness: float = 0.0
    usable_yield: float = 0.0
    provider_count: int = 0
    last_updated: datetime | None = None


class ObservabilitySnapshot(BaseModel):
    generated_at: datetime
    provider_metrics: list[ProviderMetric] = Field(default_factory=list)
    ranked_article_count: int = 0
    cluster_count: int = 0
    # Historical data (populated on explicit /observability calls)
    historical_metrics: list[HistoricalMetric] = Field(default_factory=list)
    country_quality: list[CountryQualitySnapshot] = Field(default_factory=list)
    stale_cache_warnings: list[str] = Field(default_factory=list)


class GeminiSummary(BaseModel):
    main_event: str = Field(..., description="Single headline summary of the dominant event.")
    regional_sentiment: float = Field(..., ge=-1.0, le=1.0)
    situation_report: list[str] = Field(..., min_length=3, max_length=3)


class IntelligenceResponse(BaseModel):
    country_code: str
    country_name: str
    main_event: str
    regional_sentiment: float
    situation_report: list[str]
    from_date: str
    updated_at: datetime
    articles: list[Article]
    headline_articles: list[Article] = Field(default_factory=list)
    provider_statuses: list[ProviderStatus] = Field(default_factory=list)
    summary_status: SummaryStatus
    pipeline_status: list[PipelineStatus] = Field(default_factory=list)
    cache: CacheStatus = Field(default_factory=CacheStatus)
    story_clusters: list[StoryCluster] = Field(default_factory=list)
    observability: ObservabilitySnapshot
