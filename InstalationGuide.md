# Installation and Evaluation Guide

This guide explains how to clone, configure, run, test, and evaluate the Contextual Post Explainer solution locally.

## 1. Prerequisites

Install the following tools before starting:

- Git
- Python 3.11 or newer
- `uv` for Python dependency management
- Node.js 20 or newer
- npm
- An OpenAI API key
- At least one live search provider key: Tavily or Brave

Recommended live demo configuration:

```env
SEARCH_PROVIDER=tavily
OPENAI_GENERATION_MODEL=gpt-4o
OPENAI_JUDGE_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-4o
```

These are safe defaults for evaluator access. If the evaluator key has access to newer models, the tested upgrade path is `gpt-5.1` for generation/vision and `gpt-5-mini` for judging.

The project also supports:

- `SEARCH_PROVIDER=brave`
- `SEARCH_PROVIDER=composite`, which runs every configured provider, deduplicates overlapping results, and reranks the merged evidence.

## 2. Clone the Repository

```bash
git clone https://github.com/esousaa/ContextualPostExplainer.git
cd ContextualPostExplainer
```

If the repository is cloned under a different folder name, use that folder instead of `ContextualPostExplainer`.

## 3. Configure Environment Variables

Create the root environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
OPENAI_API_KEY=<your-openai-api-key>
OPENAI_GENERATION_MODEL=gpt-4o
OPENAI_JUDGE_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-4o

APP_BACKEND_PORT=8000
APP_FRONTEND_PORT=5173
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

SEARCH_PROVIDER=tavily
TAVILY_API_KEY=<your-tavily-api-key>
BRAVE_API_KEY=

EVAL_FIXTURE_DIR=eval/fixtures
COMPARISON_GROUP_ID=
COMPARISON_CONFIG_ID=
```

Use only keys that belong to the evaluator or to the deployment environment. Do not commit `.env`.

### Search Provider Options

Tavily only:

```env
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=<your-tavily-api-key>
BRAVE_API_KEY=
```

Brave only:

```env
SEARCH_PROVIDER=brave
BRAVE_API_KEY=<your-brave-api-key>
TAVILY_API_KEY=
```

Composite search:

```env
SEARCH_PROVIDER=composite
TAVILY_API_KEY=<your-tavily-api-key>
BRAVE_API_KEY=<your-brave-api-key>
```

Composite search runs all configured providers, merges the results, deduplicates equivalent URLs/content, and reranks evidence before generation.

## 4. Choose a Setup Mode

Use the root `Makefile` to choose either Docker or local execution. Both modes use the same `make up` and `make down` lifecycle commands after setup.

### Option A: Docker Setup

```bash
make setup-docker
```

This command:

- creates `.env` from `.env.example` if it does not exist;
- validates Docker Compose;
- builds backend and frontend Docker images;
- mounts `backend/runs` into the backend container at `/app/runs`;
- stores `docker` in `.run/deploy_mode`.

### Option B: Local Setup

```bash
make setup-local
```

This command:

- creates `.env` from `.env.example` if it does not exist;
- creates `frontend/.env` from `frontend/.env.example` if it does not exist;
- installs backend dependencies with `uv sync`;
- installs frontend dependencies with `npm install`;
- stores `local` in `.run/deploy_mode`.

If setup creates `.env` for you, edit `.env` with real API keys before running live analysis. If ports `8000` or `5173` are occupied, change `APP_BACKEND_PORT` and `APP_FRONTEND_PORT` in `.env`.

Start the configured mode:

```bash
make up
```

Stop the configured mode:

```bash
make down
```

After changing `.env`, restart the services:

```bash
make down
make up
```

For later runs, use:

```bash
make up
make down
```

Service URLs:

```text
Frontend: http://localhost:${APP_FRONTEND_PORT:-5173}
Backend:  http://localhost:${APP_BACKEND_PORT:-8000}
```

Local runtime files:

```text
logs/backend.log
logs/frontend.log
.run/backend.pid
.run/frontend.pid
```

Docker runtime logs are available through `docker compose logs backend` and `docker compose logs frontend`. The `logs/` and `.run/` directories are local runtime artifacts and should not be committed.

The examples below use the default ports. If you changed `APP_BACKEND_PORT` or `APP_FRONTEND_PORT`, use the values printed by `make up`.

## 5. Verify the Backend

After starting the environment, check the backend:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/config/status
```

Expected health response:

```json
{
  "status": "ok",
  "service": "contextual-post-explainer-api",
  "version": "0.1.0"
}
```

Expected config status for a fully configured live environment:

```json
{
  "status": "ready",
  "live_search": {
    "configured": true
  },
  "diagnostics": {
    "live_mode_ready": true
  }
}
```

If `status` is `degraded`, the backend started but live mode is missing a valid search provider/key pair. Eval mode can still run from fixtures.

## 6. Run a Live Explanation

In the frontend:

1. Open `http://localhost:5173`.
2. Paste a public Bluesky post URL.
3. Click `Explain`.
4. Watch the live progress steps.
5. Review the generated bullets, source cards, warnings, and run quality indicators.

Example public Bluesky URL format:

```text
https://bsky.app/profile/<handle>/post/<rkey>
```

The current live implementation is scoped to public Bluesky posts. Other public networks are architectural extensions, not required for the current demo path.

## 7. Use Observability

After at least one run, open the Observability page from the frontend navigation.

The page reads local run artifacts generated by the backend:

```text
backend/runs/live/{run_id}.json
backend/runs/eval/{run_id}.json
```

Use Observability to inspect:

- Pipeline timeline and node durations
- Original post payload
- Final explanation and warnings
- Retrieved, ranked, and cited sources
- Generated search queries
- Diagnostics and raw artifact data
- Citation repair audit data when repair was attempted

Run artifacts are written locally and secrets are redacted before persistence.

## 8. Use Comparative Analysis

Open the Analysis page from the frontend navigation.

The Analysis page compares two dimensions:

- Search Provider performance: Tavily, Brave, and Composite
- LLM stack performance: generation model, judge model, embedding model, and vision model

The dashboard aggregates local run artifacts and shows comparative cards, charts, and behavior changes by URL.

To make comparisons meaningful, run the same set of URLs under each configuration and keep the same `COMPARISON_GROUP_ID`.

Example search provider benchmark:

```env
COMPARISON_GROUP_ID=search-provider-benchmark
SEARCH_PROVIDER=tavily
```

Then repeat with:

```env
SEARCH_PROVIDER=brave
```

And:

```env
SEARCH_PROVIDER=composite
```

Restart services after changing `.env`:

```bash
make down
make up
```

## 9. Run the Backend Test Suite

```bash
make backend-test
```

Equivalent command:

```bash
cd backend
uv run pytest
```

Run backend lint:

```bash
make backend-lint
```

Equivalent command:

```bash
cd backend
uv run ruff check .
```

## 10. Run the Frontend Checks

```bash
make frontend-lint
make frontend-test
make frontend-build
```

Equivalent commands:

```bash
cd frontend
npm run lint
npm run test
npm run build
```

## 11. Run the Eval Harness

The eval harness uses local fixtures for posts and evidence. It does not call Bluesky, Brave, Tavily, or live web pages. It can still call OpenAI for generation, embeddings, and groundedness judging.

```bash
make eval
```

Outputs:

```text
eval/results/latest.json
eval/results/latest.md
backend/runs/eval/{run_id}.json
```

The eval dataset contains 12 cases, including:

- Thread context
- External links
- Quote posts
- Image alt text
- OCR/image text extraction
- Low-evidence refusal
- Groundedness assessment

## 12. Docker Details

The repository includes Docker Compose for backend and frontend services.

Recommended Docker workflow:

```bash
make setup-docker
make up
```

Service URLs:

```text
Frontend: http://localhost:${APP_FRONTEND_PORT:-5173}
Backend:  http://localhost:${APP_BACKEND_PORT:-8000}
```

Stop Docker services through the same lifecycle command:

```bash
make down
```

The Docker path reads the root `.env` file. Make sure it is configured before starting the stack. To avoid port conflicts, set `APP_BACKEND_PORT` and `APP_FRONTEND_PORT` before running `make up`.

Docker Compose mounts the repository's local `backend/runs` folder into the backend container at `/app/runs`. This means:

- cloned historical run artifacts are visible in Observability and Analysis as soon as the stack starts;
- new live/eval/comparison runs generated inside Docker are saved back to `backend/runs` on the host;
- removing or recreating the container does not delete run artifacts.

`make setup-docker` and Docker `make up` prepare this folder with write permissions so the backend container can append new run artifacts on a fresh clone.

## 13. Manual Development Commands

Use these only when you want foreground processes in separate terminals.

Backend:

```bash
make backend-run
```

Frontend:

```bash
make frontend-run
```

Manual dependency installation:

```bash
cd backend
uv sync

cd ../frontend
npm install
cp .env.example .env
```

The frontend environment file should point to the backend API:

```env
VITE_API_BASE_URL=http://localhost:8000
```

When using `make up`, `VITE_API_BASE_URL` is injected from `APP_BACKEND_PORT`, so manual edits are only needed for standalone frontend development.

## 14. Troubleshooting

### `/api/config/status` returns `invalid`

Required environment variables are missing or malformed. Check `.env`, especially:

- `OPENAI_API_KEY`
- `OPENAI_GENERATION_MODEL`
- `OPENAI_JUDGE_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `BACKEND_CORS_ORIGINS`
- `EVAL_FIXTURE_DIR`

### `/api/config/status` returns `degraded`

The backend can start, but live mode is not ready. Check:

- `SEARCH_PROVIDER`
- `TAVILY_API_KEY` when using Tavily
- `BRAVE_API_KEY` when using Brave
- At least one provider key when using Composite

### Frontend cannot reach the backend

Check `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Restart the frontend after changing this file:

```bash
make down
make up
```

### Live run returns no bullets

This can be a valid outcome. The system returns zero bullets when the retrieved evidence cannot safely support a 3 to 5 bullet explanation under the citation compatibility contract.

Check Observability for:

- Search queries
- Source fetch discards
- Ranking discards
- Citation compatibility warnings
- Repair attempts and repair audit data

### Image text is missing

Confirm that `OPENAI_VISION_MODEL` is configured. Without a vision model, the system can still use Bluesky alt text, but it cannot perform image OCR or visual description.

### Runs are slow

Use the Observability timeline to identify the slow node. Typical slow areas are:

- Search provider latency
- Source page fetching/parsing
- OpenAI generation
- OpenAI vision analysis for image posts

### `make up` says a port is already in use

Another process is already listening on the configured backend or frontend port. Stop that process or change `APP_BACKEND_PORT` / `APP_FRONTEND_PORT` in `.env`, then run:

```bash
make down
make up
```

## 15. Recommended Demo Sequence

1. Configure `.env` with OpenAI and search provider keys.
2. Run `make setup-docker` or `make setup-local`, depending on the execution mode you want to validate.
3. Run `make up`.
4. Check `http://localhost:8000/api/health`.
5. Check `http://localhost:8000/api/config/status`.
6. Open `http://localhost:5173`.
7. Run one public Bluesky post in Explain.
8. Open Observability and inspect the run timeline, sources, warnings, and repair audit if present.
9. Run the same URL under another search provider or model stack.
10. Open Analysis and compare Search Provider and LLM outcomes.
11. Run `make backend-test`.
12. Run `make frontend-lint`, `make frontend-test`, and `make frontend-build`.
13. Stop services with `make down`.
