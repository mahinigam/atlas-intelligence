# Atlas.Intelligence

Real-time geopolitical intelligence platform. Multi-provider news ingestion → AI summarization → interactive 3D map. 1,700+ lines of pipeline logic, 45-country knowledge base, 81-domain source reputation system.

## What It Does

Click a country on the map → the backend fans out to **6 news APIs in parallel**, deduplicates via canonical URL normalization, scores every article against a curated **source reputation table** (Reuters 0.98 → InfoWars 0.15), ranks by entity-density relevance using a **structured country knowledge base** (capitals, leaders, ministries, demonyms, aliases), clusters stories with **Jaccard n-gram similarity**, then feeds the top articles to **Gemini Flash** for a structured situation report with sentiment analysis. The frontend renders it on a MapLibre GL globe with sentiment-driven color feedback in real time.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Next.js 16 (App Router)                                     │
│  MapLibre GL · Framer Motion · Tailwind v4                   │
│  Components: WorldMap, CommandCenter, ProviderPanel           │
│              SentimentGauge, NewsCard, TimeTravelSlider        │
└────────────────────────┬─────────────────────────────────────┘
                         │ REST
┌────────────────────────▼─────────────────────────────────────┐
│  FastAPI                                                      │
│  /intelligence → fetch_country_news → summarize_articles      │
│  /observability → historical metrics + country quality        │
│                                                               │
│  Pipeline: 6 providers → dedupe → rank → cluster → summarize │
│  Services: source_reputation · country_metadata · cache       │
│  Infra: Redis (cache + time-series metrics)                   │
└──────────────────────────────────────────────────────────────┘
         ▼              ▼              ▼            ▼
   World News    NewsCatcher    GNews    Currents   ...
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind v4, Framer Motion, MapLibre GL JS, Lucide |
| Backend | FastAPI, Pydantic v2, httpx (async), Redis |
| AI | Gemini 1.5 Flash (structured JSON generation) |
| News Providers | World News API, NewsCatcher, GNews, Currents, NewsAPI.org, NewsData.io |
| Observability | Redis time-series, per-provider historical metrics, country quality snapshots |

## Engineering Highlights

- **Multi-provider orchestration** — 6 APIs fetched concurrently via `asyncio.gather`, per-provider timeout budgets, circuit-breaker cooldowns, learned fallback ordering from production usage history
- **Source reputation system** — 81 curated domains with trust scores, Redis-persisted for runtime evolution, blended 65/35 with provider quality for article scoring
- **Country knowledge base** — 45 countries with structured `CountryInfo` dataclass (8 fields: capital, leader titles, ministries, regions, demonyms, aliases, cities, key entities) driving entity-density relevance scoring
- **Article deduplication** — Canonical URL normalization (tracking param stripping, query sorting, scheme normalization) + content fingerprinting
- **Jaccard n-gram clustering** — Word-level bigram sets with SequenceMatcher confirmation to group stories across providers without false positives
- **Persistent observability** — Every provider fetch appends a timestamped metric to Redis; `/observability` returns historical latency, success rates, country coverage quality, and stale-cache warnings
- **Graceful degradation** — Missing API keys → deterministic synthetic feed; all providers down → fallback content with transparent pipeline status flags; no Redis → in-memory no-op cache

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv312 && source .venv312/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in API keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local  # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `REDIS_URL` | Redis connection (cache + metrics). Falls back to in-memory if unavailable |
| `GEMINI_API_KEY` | Gemini Flash for AI summarization |
| `GEMINI_API_URL` | Gemini `generateContent` endpoint |
| `GNEWS_API_KEY` | GNews provider |
| `WORLDNEWS_API_KEY` | World News API provider |
| `NEWSCATCHER_API_KEY` | NewsCatcher provider |
| `NEWSAPI_ORG_API_KEY` | NewsAPI.org provider |
| `CURRENTS_API_KEY` | Currents API provider |
| `NEWSDATA_API_KEY` | NewsData.io provider |

### Frontend (`frontend/.env.local`)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL (`http://localhost:8000` locally) |
| `NEXT_PUBLIC_COUNTRIES_GEOJSON_URL` | GeoJSON path for map boundaries |
| `NEXT_PUBLIC_MAP_STYLE_URL` | Optional MapLibre style URL |

## Deployment

### Frontend → Vercel

1. **Import the repo** in [vercel.com/new](https://vercel.com/new).
2. **Set root directory** to `frontend`.
3. **Framework preset**: Next.js (auto-detected).
4. **Environment variables** — add in Vercel dashboard → Settings → Environment Variables:
   ```
   NEXT_PUBLIC_API_BASE_URL=https://your-backend.railway.app
   NEXT_PUBLIC_COUNTRIES_GEOJSON_URL=/data/countries.geojson
   ```
5. **Deploy**. Vercel handles `npm install && next build` automatically.

> If you get a build error about `useEffectEvent`, ensure your `next` version is `>=16.0.0` (React 19 experimental API).

### Backend → Railway / Render / Fly.io

The backend is a standard FastAPI app with a `Dockerfile`:

```bash
# Railway (one-click)
railway login && railway init && railway up

# Or Render / Fly.io via Dockerfile
docker build -t atlas-backend ./backend
docker run -p 8000:8000 --env-file backend/.env atlas-backend
```

Set all backend env vars in your hosting provider's dashboard. Redis can use **Upstash** (free tier, serverless) or **Railway Redis**.

### CORS

The backend allows all origins by default. For production, update `CORSMiddleware` in `main.py` to whitelist only your Vercel domain.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/intelligence?country_code=USA&from_date=2026-03-20` | Full intelligence pipeline |
| `GET` | `/api/v1/countries` | Supported country list |
| `GET` | `/api/v1/observability` | System health + historical metrics |
| `GET` | `/api/v1/observability/providers/{provider}` | Per-provider historical data |

## Project Structure

```
atlas.intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI routes
│   │   ├── config.py            # Settings (env-driven)
│   │   ├── schemas.py           # Pydantic models
│   │   ├── cache.py             # Redis client with time-series
│   │   ├── country_metadata.py  # 45-country knowledge base
│   │   ├── dependencies.py      # DI for httpx + Redis
│   │   └── services/
│   │       ├── news.py          # 1,700-line pipeline engine
│   │       ├── source_reputation.py  # 81-domain trust table
│   │       └── summarizer.py    # Gemini orchestration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                     # Next.js App Router
│   ├── components/
│   │   ├── CommandCenter.tsx    # Main orchestration component
│   │   ├── WorldMap.tsx         # MapLibre GL 3D map
│   │   ├── ProviderPanel.tsx    # Provider health panel
│   │   ├── NewsCard.tsx         # Article cards with scoring
│   │   ├── SentimentGauge.tsx   # Sentiment speedometer
│   │   ├── StatusBar.tsx        # Global status footer
│   │   └── TimeTravelSlider.tsx # Date range control
│   └── lib/
│       ├── api.ts               # Backend API client
│       └── types.ts             # TypeScript type definitions
└── README.md
```
