"""Source reputation management — maintains trust scores for news domains.

The reputation table is seeded with a curated set of ~80 authoritative sources
and persisted to Redis so it can evolve over time.  The cache key is
``atlas:source_reputation`` and the shape is ``{domain: score}``.
"""

from __future__ import annotations

import logging
from typing import Any

from app.cache import CacheClient

logger = logging.getLogger(__name__)

# ── Seed Reputation Table ─────────────────────────────────────────────────
# Scores: 0.0 (untrustworthy) → 1.0 (gold-standard wire service)
# Maintained as a flat dict; persisted to Redis for runtime evolution.
# Re-seeded automatically if Redis key is missing.

_SEED_REPUTATION: dict[str, float] = {
    # Wire services & major agencies
    "reuters.com": 0.98,
    "apnews.com": 0.97,
    "afp.com": 0.96,
    "upi.com": 0.90,
    # US broadsheets
    "nytimes.com": 0.94,
    "washingtonpost.com": 0.93,
    "wsj.com": 0.93,
    "usatoday.com": 0.82,
    "latimes.com": 0.86,
    "politico.com": 0.88,
    "thehill.com": 0.84,
    "axios.com": 0.86,
    # UK broadsheets
    "bbc.com": 0.95,
    "bbc.co.uk": 0.95,
    "theguardian.com": 0.91,
    "ft.com": 0.94,
    "thetimes.co.uk": 0.89,
    "telegraph.co.uk": 0.86,
    "independent.co.uk": 0.83,
    "economist.com": 0.93,
    # European
    "dw.com": 0.90,
    "france24.com": 0.89,
    "lemonde.fr": 0.88,
    "elpais.com": 0.87,
    "spiegel.de": 0.87,
    "ansa.it": 0.86,
    "rte.ie": 0.85,
    "swissinfo.ch": 0.86,
    # Middle East
    "aljazeera.com": 0.90,
    "alarabiya.net": 0.82,
    "thenationalnews.com": 0.84,
    "middleeasteye.net": 0.80,
    "timesofisrael.com": 0.83,
    "haaretz.com": 0.85,
    "jpost.com": 0.80,
    # Asia-Pacific
    "scmp.com": 0.88,
    "nikkei.com": 0.91,
    "japantimes.co.jp": 0.85,
    "straitstimes.com": 0.87,
    "channelnewsasia.com": 0.86,
    "thehindu.com": 0.86,
    "ndtv.com": 0.83,
    "hindustantimes.com": 0.82,
    "timesofindia.indiatimes.com": 0.80,
    "indianexpress.com": 0.84,
    "koreaherald.com": 0.82,
    "koreajoongangdaily.joins.com": 0.81,
    "bangkokpost.com": 0.80,
    "abc.net.au": 0.89,
    "smh.com.au": 0.85,
    "rnz.co.nz": 0.86,
    "dawn.com": 0.82,
    "geo.tv": 0.78,
    # Africa
    "africanews.com": 0.80,
    "news24.com": 0.78,
    "allafrica.com": 0.76,
    "dailymaverick.co.za": 0.82,
    "premiumtimesng.com": 0.78,
    "nation.africa": 0.77,
    # Latin America
    "globo.com": 0.82,
    "infobae.com": 0.80,
    "eluniversal.com.mx": 0.79,
    # Financial & business
    "bloomberg.com": 0.95,
    "cnbc.com": 0.87,
    "marketwatch.com": 0.84,
    "finance.yahoo.com": 0.78,
    "investing.com": 0.75,
    # Technology
    "techcrunch.com": 0.82,
    "theverge.com": 0.80,
    "arstechnica.com": 0.83,
    "wired.com": 0.82,
    # Penalty-tier (tabloid / opinion-heavy)
    "nypost.com": 0.62,
    "dailymail.co.uk": 0.55,
    "thesun.co.uk": 0.50,
    "mirror.co.uk": 0.52,
    "foxnews.com": 0.68,
    "breitbart.com": 0.40,
    "infowars.com": 0.15,
    "rt.com": 0.35,
    "sputniknews.com": 0.30,
    "globalresearch.ca": 0.20,
}

# Default score for unknown domains
_DEFAULT_SCORE = 0.58


async def load_reputation_table(cache: CacheClient) -> dict[str, float]:
    """Load the reputation table from Redis, seeding it if missing."""
    cached = await cache.get_json("atlas:source_reputation")
    if cached:
        return {k: float(v) for k, v in cached.items()}

    # Seed from the built-in table
    await cache.set_json("atlas:source_reputation", _SEED_REPUTATION)
    logger.info("Seeded source reputation table with %d entries", len(_SEED_REPUTATION))
    return dict(_SEED_REPUTATION)


async def get_source_trust(cache: CacheClient, domain: str) -> float:
    """Return the trust score for a domain, falling back to the default."""
    table = await load_reputation_table(cache)
    domain = domain.lower().removeprefix("www.")
    return table.get(domain, _DEFAULT_SCORE)


async def update_source_trust(cache: CacheClient, domain: str, score: float) -> None:
    """Persist an updated trust score for a domain."""
    table = await load_reputation_table(cache)
    table[domain.lower().removeprefix("www.")] = max(0.0, min(1.0, score))
    await cache.set_json("atlas:source_reputation", table)


def get_source_trust_sync(domain: str) -> float:
    """Synchronous fallback for contexts where cache is unavailable."""
    domain = domain.lower().removeprefix("www.")
    return _SEED_REPUTATION.get(domain, _DEFAULT_SCORE)
