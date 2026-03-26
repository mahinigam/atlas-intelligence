# Atlas.Intelligence

Atlas.Intelligence is a geopolitical news analysis app: a FastAPI backend pulls articles from multiple providers, ranks and deduplicates them, and a Next.js frontend renders the result as a map-driven command center.

The project is strongest where it chooses signal over spectacle. It does not just fetch headlines. It scores source quality, filters weak country matches, clusters overlapping stories, and degrades cleanly when providers, Redis, or AI summarization are unavailable.

## What It Does

- Select a country on the map.
- Fetch news from six providers in parallel.
- Normalize and deduplicate overlapping coverage.
- Rank articles using country metadata, freshness, provider performance, and source reputation.
- Cluster related stories into a smaller representative set.
- Generate a concise situation report and sentiment score when Gemini is configured.
- Expose provider health and observability data alongside the user-facing result.

## Why This Repo Is Interesting

- The backend pipeline is substantial. [`backend/app/services/news.py`](/Users/mahinigam/Codes/Atlas.Intelligence/atlas.intelligence/backend/app/services/news.py) is 1,695 lines and contains the real ranking, deduplication, provider fallback, and clustering logic.
- The country model is not superficial. [`backend/app/country_metadata.py`](/Users/mahinigam/Codes/Atlas.Intelligence/atlas.intelligence/backend/app/country_metadata.py) holds a structured knowledge base used to improve relevance scoring.
- The frontend has a clear product point of view. The interface is not a template dashboard; it is a map-first command surface with opinionated visual styling.
- The app is resilient by design. Missing API keys, empty providers, AI quota failures, and Redis outages all have explicit fallback behavior instead of silent failure.

## Architecture

```text
Frontend (Next.js 16, React 19, TypeScript)
  -> MapLibre globe and command-center UI
  -> Calls REST API for country intelligence

Backend (FastAPI, httpx, Pydantic, Redis)
  -> Concurrent provider fetch
  -> Article normalization and deduplication
  -> Country-aware relevance ranking
  -> Story clustering
  -> Gemini summarization
  -> Observability snapshots and provider metrics
```

## Stack

| Layer | Tools |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4, Framer Motion, MapLibre GL |
| Backend | FastAPI, httpx, Pydantic v2, Redis |
| AI | Gemini Flash via HTTP API |
| News providers | World News API, NewsCatcher, GNews, Currents, NewsAPI.org, NewsData.io |

## Repository Layout

```text
atlas.intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── cache.py
│   │   ├── country_metadata.py
│   │   ├── schemas.py
│   │   └── services/
│   │       ├── news.py
│   │       ├── source_reputation.py
│   │       └── summarizer.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── public/data/
└── README.md
```

## Local Development

### Backend

```bash
cd backend
python -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Frontend default: `http://localhost:3000`  
Backend default: `http://localhost:8000`

## Environment Variables

### Backend

| Variable | Purpose |
| --- | --- |
| `REDIS_URL` | Cache and observability storage |
| `GEMINI_API_KEY` | Enables AI summarization |
| `GEMINI_API_URL` | Optional override for the Gemini endpoint |
| `WORLDNEWS_API_KEY` | World News API |
| `NEWSCATCHER_API_KEY` | NewsCatcher |
| `GNEWS_API_KEY` | GNews |
| `CURRENTS_API_KEY` | Currents |
| `NEWSAPI_ORG_API_KEY` | NewsAPI.org |
| `NEWSDATA_API_KEY` | NewsData.io |

If `GEMINI_API_KEY` is missing, the app still works, but returns ranked raw reporting instead of AI-generated summaries.

### Frontend

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL |
| `NEXT_PUBLIC_COUNTRIES_GEOJSON_URL` | Country geometry source |
| `NEXT_PUBLIC_MAP_STYLE_URL` | Optional MapLibre style URL |

## API Surface

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Basic health check |
| `GET` | `/api/v1/countries` | Supported countries |
| `GET` | `/api/v1/intelligence` | Ranked articles plus summary for one country |
| `GET` | `/api/v1/intelligence/stream` | Streaming variant of the intelligence response |
| `GET` | `/api/v1/observability` | Global observability snapshot |
| `GET` | `/api/v1/observability/providers/{provider}` | Historical metrics for one provider |

Example:

```bash
curl "http://localhost:8000/api/v1/intelligence?country_code=IND"
```

## Tests

The backend tests currently expect `backend` on `PYTHONPATH`.

```bash
PYTHONPATH=backend backend/.venv312/bin/pytest backend/tests -q
```

Current result in this workspace: `5 passed`.

## Deployment Notes

- Frontend deploys cleanly to Vercel as a standard Next.js app.
- Backend can run on Railway, Render, Fly.io, or any container host with Redis access.
- CORS is currently open in [`backend/app/main.py`](/Users/mahinigam/Codes/Atlas.Intelligence/atlas.intelligence/backend/app/main.py). Lock that down before production.

## Current Strengths

- Strong backend logic relative to project size.
- Clear product framing and coherent UX direction.
- Real observability and fallback behavior, not just happy-path demos.

## Current Gaps

- Test execution depends on `PYTHONPATH`, which should be fixed in repo tooling.
- The README and env examples need to stay aligned with the actual Gemini endpoint strategy.
- Production hardening is not finished yet: open CORS, local-first setup, and limited test breadth make that clear.
