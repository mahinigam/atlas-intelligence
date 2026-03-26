from datetime import datetime

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class Article(BaseModel):
    title: str
    source: str
    url: str
    published_at: datetime | None = None
    snippet: str = ""


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
