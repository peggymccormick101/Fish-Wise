# FishWise

Link to app: https://fishwise.onrender.com/

Find a body of water, tell it what season it is, and get practical fishing
advice: likely species, recommended hooks/bait/line, and concrete techniques
to try — powered by Claude.

## How it works

1. Enter a body of water (e.g. "Lake Travis, TX").
2. FishWise geocodes it (LocationIQ), asks Claude which species are commonly
   found there, and looks up real current weather + today's sunrise/sunset
   for that location (Open-Meteo).
3. Pick a species and a season.
4. Get a full set of tips: best conditions, recommended gear by category, and
   step-by-step techniques.
5. Past searches are saved so you can revisit or delete them later.

## Stack

- **Backend:** FastAPI + SQLAlchemy (SQLite) + the Claude API (`anthropic`
  Python SDK) for species/tips, LocationIQ for geocoding, and Open-Meteo for
  current weather + sunrise/sunset
- **Frontend:** React (Vite) + React Router

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then edit .env: set ANTHROPIC_API_KEY and LOCATIONIQ_API_KEY
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`LOCATIONIQ_API_KEY` is a free key (5,000 requests/day, no card required) —
sign up at [locationiq.com](https://locationiq.com). It's used to turn a
water body name into coordinates; Open-Meteo (weather/sun times) needs no
key of its own.

The API runs at `http://localhost:8000` (docs at `/docs`). It creates
`backend/fishwise.db` (SQLite) on first run.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5173` and proxies `/api` requests to the
backend on port 8000 (see `vite.config.js`).

## API

- `POST /api/waterbodies/lookup` — identify a water body, suggest species,
  and return current conditions (temperature, wind, sunrise/sunset) for it
- `POST /api/searches` — generate and save fishing tips for a water
  body/species/season combo
- `GET /api/searches` — list saved searches
- `GET /api/searches/{id}` — get a search's full tips
- `DELETE /api/searches/{id}` — delete a saved search

## Deployment (Render)

The app deploys as a single service: a Docker image builds the React
frontend, then FastAPI serves both the API (`/api/*`) and the built
frontend (everything else) from one process.

1. Push this repo to GitHub (already done if you're reading this from there).
2. On [render.com](https://render.com), sign up / log in, then **New >
   Blueprint**, and point it at this repo. Render reads `render.yaml`
   automatically and creates the service.
3. When prompted, enter your `ANTHROPIC_API_KEY`, `LOCATIONIQ_API_KEY` (and
   `ANTHROPIC_WORKSPACE_ID` if your account requires one — see
   `backend/.env.example`) as the service's environment variables. These are
   entered directly in Render's dashboard, never committed to the repo.
4. Deploy. Render builds the Docker image (`Dockerfile` at the repo root)
   and gives you a public `https://fishwise-xxxx.onrender.com` URL.

**Note on data:** the free tier's disk is ephemeral — the SQLite database
(saved searches) resets on every redeploy. That's fine for personal/testing
use; if persistence across deploys matters later, that would mean adding a
Render persistent disk or switching to a hosted database.
