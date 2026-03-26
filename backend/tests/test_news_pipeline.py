import json
from pathlib import Path
from datetime import datetime, timezone

from app.config import Settings
from app.schemas import Article
from app.services.news import _cluster_articles, _deduplicate_articles, _normalize_text, _rank_articles


def test_deduplicate_articles_merges_provider_variants() -> None:
    articles = [
        Article(
            title="France protests expand across Paris",
            source="Reuters",
            provider="gnews",
            providers=["gnews"],
            url="https://example.com/story?utm_source=x",
            canonical_url="https://example.com/story",
            snippet="Police and unions faced a second day of demonstrations in Paris.",
            published_at=datetime(2026, 3, 25, 12, 0, tzinfo=timezone.utc),
        ),
        Article(
            title="France protests expand across Paris",
            source="Reuters",
            provider="newsdata",
            providers=["newsdata"],
            url="https://example.com/story",
            canonical_url="https://example.com/story",
            snippet="Police and unions faced demonstrations in Paris as transport routes closed.",
            published_at=datetime(2026, 3, 25, 11, 0, tzinfo=timezone.utc),
        ),
    ]

    deduped = _deduplicate_articles(articles)

    assert len(deduped) == 1
    assert deduped[0].providers == ["gnews", "newsdata"]
    assert "transport routes closed" in deduped[0].snippet


def test_rank_articles_filters_weak_country_matches() -> None:
    settings = Settings(news_min_relevance_score=0.35)
    articles = [
        Article(
            title="India parliament debates new transport budget",
            source="Reuters",
            provider="gnews",
            providers=["gnews"],
            url="https://example.com/india",
            canonical_url="https://example.com/india",
            snippet="New Delhi lawmakers advanced transport and defense spending after a late debate.",
            published_at=datetime.now(timezone.utc),
        ),
        Article(
            title="Global markets rally on chipmaker forecast",
            source="Bloomberg",
            provider="newsdata",
            providers=["newsdata"],
            url="https://example.com/markets",
            canonical_url="https://example.com/markets",
            snippet="Stocks climbed in Europe and the United States after a strong earnings forecast.",
            published_at=datetime.now(timezone.utc),
        ),
    ]

    ranked = _rank_articles(country_code="IND", settings=settings, articles=articles)

    assert len(ranked) == 1
    assert ranked[0].title == "India parliament debates new transport budget"
    assert ranked[0].relevance_score >= settings.news_min_relevance_score


def test_normalize_text_strips_html_and_boilerplate() -> None:
    cleaned = _normalize_text("<p>Headline</p> read more [+123 chars]")

    assert cleaned == "Headline"


def test_regression_fixture_clusters_and_ranks() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "provider_samples.json"
    payload = json.loads(fixture_path.read_text())
    articles = [Article.model_validate(article) for article in payload["articles"]]

    deduped = _deduplicate_articles(articles)
    ranked = _rank_articles(country_code="IND", settings=Settings(), articles=deduped)
    clusters = _cluster_articles(ranked)

    assert len(deduped) == 1
    assert ranked[0].evidence_points
    assert ranked[0].confidence in {"medium", "high"}
    assert len(clusters) == 1
