# Atlas.Intelligence

Retro-claymorphic global event command center with a Next.js frontend and FastAPI backend. Users click a country on the map, trigger a country-scoped news lookup, and receive an AI-generated situation report with sentiment-aware map feedback.

## Stack

- Frontend: Next.js 16 App Router, Tailwind CSS v4, Framer Motion, MapLibre GL JS
- Backend: FastAPI, httpx, Redis cache layer
- AI orchestration: Gemini 1.5 Flash via Vertex AI-compatible REST call
- Data services: GNews or NewsData.io
- Spatial persistence target: PostgreSQL + PostGIS

## Project Layout

- `frontend/`: Next.js command center UI
- `backend/`: FastAPI intelligence API

## Local Setup

### Frontend

1. Copy `frontend/.env.example` to `frontend/.env.local`.
2. Install dependencies with `npm install`.
3. Run `npm run dev`.

### Backend

1. Create a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env`.
4. Run `uvicorn app.main:app --reload` from `backend/`.

## Required Environment Variables

### Frontend

- `NEXT_PUBLIC_API_BASE_URL`: FastAPI base URL, for example `http://localhost:8000`

### Backend

- `REDIS_URL`: Redis instance used for the 15-minute cache
- `POSTGRES_DSN`: Postgres/PostGIS DSN for future spatial persistence
- `GEMINI_API_KEY`: Vertex/Gemini key
- `GEMINI_API_URL`: Gemini `generateContent` endpoint
- `GNEWS_API_KEY`: Optional primary news provider
- `NEWSDATA_API_KEY`: Optional fallback news provider

## Behavior Notes

- The map is rendered behind a Suspense boundary.
- The time-travel slider changes the `from_date` parameter used by the backend.
- Redis cache keys are scoped by `country_code` and `from_date`.
- If external API keys are missing, the backend returns deterministic placeholder content instead of failing hard.

## Deployment

### Vercel

- Deploy `frontend/` as a Next.js project.
- Set `NEXT_PUBLIC_API_BASE_URL` to the deployed backend URL.

### Hugging Face Spaces

- Deploy `backend/` as a Docker Space using the included `backend/Dockerfile`.
- Expose port `8000`.

## Next Extensions

- Replace static country metadata with PostGIS reverse lookups from clicked coordinates.
- Add translation controls by passing the user locale into the Gemini prompt.
- Swap demo vector tiles for a production world boundary tileset with stable `iso_a3` attributes.
