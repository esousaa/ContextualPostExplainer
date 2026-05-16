# Contextual Post Explainer

An AI agent that explains Bluesky social media posts by searching for relevant public context, ranking evidence, and returning 3–5 cited explanatory bullets.

Built as a technical exercise for RapidCanvas. The system takes a public Bluesky post URL, decomposes it into search queries, retrieves and reads real web pages, ranks sources by semantic relevance, and generates a structured explanation with verifiable citations — refusing to produce bullets when the evidence cannot safely support them.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture Overview](#architecture-overview)
- [Agent Methodology](#agent-methodology)
- [Source Control and Citation Safety](#source-control-and-citation-safety)
- [Warnings and Refusal Behavior](#warnings-and-refusal-behavior)
- [Key Design Decisions](#key-design-decisions)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
  - [Docker](#docker)
  - [Without Docker](#without-docker)
- [Configuration](#configuration)
- [Running the Evaluation Harness](#running-the-evaluation-harness)
- [API Reference](#api-reference)
- [Search Providers](#search-providers)
- [Multi-Provider Comparison](#multi-provider-comparison)
- [Image Understanding](#image-understanding)
- [What I Would Do With More Time](#what-i-would-do-with-more-time)

---

![Interface demo](docs/assets/rapidcanvas-case.gif)

## What It Does

Paste a Bluesky post URL into the interface. The agent:

1. Fetches the post and its thread context via the public AT Protocol API (no authentication required).
2. Optionally analyzes any images with GPT vision (OCR + visual description).
3. Decomposes the post into 2–4 targeted search queries using an LLM.
4. Searches the web through a configured provider (Brave, Tavily, or both in parallel).
5. Downloads and reads the actual content of each result page — not just the search snippet.
6. Ranks all evidence using OpenAI embeddings and cosine similarity.
7. Generates 3–5 cited explanatory bullets using OpenAI structured outputs.
8. Validates every citation structurally and semantically before returning a response.

If the evidence cannot safely support a full explanation, the system returns an empty `explanation` array with warnings rather than producing unsupported claims.

**Example output for a post about the "Ralph Wiggum technique" for AI coding agents:**

> - The "Ralph Wiggum technique" is a bash-loop approach for running AI coding agents iteratively until tasks complete, named after The Simpsons character for its trial-and-error style. `[source 1]`
> - It was coined by Geoffrey Huntley in mid-2025 and gained traction for its simplicity over elaborate agentic frameworks. `[source 1, 2]`
> - The name spawned derivatives including the $RALPH Solana token. `[source 3]`

---

## Architecture Overview

```
React UI  (Vite + TypeScript + custom CSS)
    │
    │  POST /api/explain  (SSE streaming available at /api/explain/stream)
    ▼
FastAPI  (Python 3.11 + Uvicorn)
    │
    ├── LiveExplanationService
    │       └── LiveExplanationFlow  (LangGraph StateGraph)
    │             ├── validate_live_config
    │             ├── parse_post_url
    │             ├── fetch_bluesky_post_thread   ← AT Protocol, no auth
    │             ├── analyze_images_optional      ← multimodal image analysis step (if OPENAI_VISION_MODEL is set)
    │             ├── decompose_queries            ← LLM → 2–4 queries
    │             ├── search_web_context           ← Brave / Tavily / Composite
    │             ├── fetch_source_pages           ← reads actual page content
    │             ├── rank_evidence                ← embeddings + cosine similarity
    │             ├── generate_explanation         ← structured output JSON
    │             ├── validate_citations           ← structural + semantic guard
    │             ├── repair_once_if_needed        ← one LLM repair pass for citation compatibility
    │             └── finalize_response
    │
    ├── EvalExplanationService
    │       └── EvalExplanationFlow  (LangGraph StateGraph)
    │             ├── load_fixture_post            ← no live Bluesky calls
    │             ├── load_fixture_evidence        ← no live search calls
    │             ├── rank_evidence                ← same ranker as live
    │             ├── generate_explanation         ← same generator as live
    │             ├── validate_citations
    │             ├── repair_once_if_needed
    │             ├── judge_groundedness           ← LLM-as-judge per bullet
    │             └── score_case                   ← 5 metrics
    │
    └── Analysis API  (GET /api/analysis)
            └── aggregates run artifacts for provider/model comparison
```

**Backend layers:**

| Layer | Responsibility |
|---|---|
| `api/` | FastAPI routes, HTTP error mapping, SSE streaming |
| `application/` | Service orchestration, flow wiring, report generation |
| `graphs/` | LangGraph StateGraphs and node implementations |
| `domain/` | Models, policies, citation validation, deduplication |
| `ports/` | Internal Protocol interfaces for all external dependencies |
| `adapters/` | Bluesky, Brave, Tavily, Composite, OpenAI, HTTP, eval fixtures |
| `observability/` | Structured logging (structlog), OpenTelemetry, run artifacts, secret redaction |
| `eval/` | Eval runner, 5-metric scoring, groundedness judge |

---

## Agent Methodology

The core design is intentionally more than "LLM + search". The agent is implemented as an auditable LangGraph workflow where each node has a narrow responsibility, typed state, run-level telemetry, and clear failure behavior.

| Node | Role | Guardrail provided |
|---|---|---|
| `validate_live_config` | Verifies live-mode dependencies before work starts | Prevents silent fallback when no search provider is configured |
| `parse_post_url` | Parses only public Bluesky post URLs | Rejects unsupported or malformed URLs before external calls |
| `fetch_bluesky_post_thread` | Fetches the post, author, parent, quote, replies, links, and images | Normalizes platform-specific data into `PostData` |
| `analyze_images_optional` | Extracts visible text, visual description, and image type | Adds image context without treating image text as independently confirmed fact |
| `decompose_queries` | Uses the LLM to create focused web-search queries | Converts informal social text into searchable context anchors |
| `search_web_context` | Calls Tavily, Brave, or both through composite search | Keeps search provider behavior replaceable and measurable |
| `fetch_source_pages` | Downloads and parses actual page content | Avoids citing search snippets the model did not really read |
| `rank_evidence` | Embeds post and source text, then ranks by cosine similarity | Reduces context noise before generation |
| `generate_explanation` | Produces JSON Schema structured bullets | Enforces predictable fields for citation validation |
| `validate_citations` | Checks source IDs and claim-source compatibility | Blocks unsupported factual claims and weak citations |
| `repair_once_if_needed` | Performs one repair pass when citation compatibility fails | Tries to reclassify or rewrite useful context before removal |
| `finalize_response` | Writes the run artifact and returns the final response | Preserves traceability for observability and analysis |

Live and eval flows are separate graphs. Live mode calls Bluesky and real search providers; eval mode uses fixtures only. They share ranking, generation, citation validation, and repair logic so evaluation exercises the same safety contract as runtime without accidentally depending on live web conditions.

---

## Source Control and Citation Safety

The source pipeline treats relevance and citation suitability as different questions. A page can be topically relevant and still be unsuitable for a specific claim.

1. **Search retrieval:** The system queries Tavily, Brave, or the composite provider.
2. **Deduplication:** Results are canonicalized, tracking parameters are removed, and duplicates are merged by URL, title, and content hash.
3. **Real page reading:** Candidate sources are fetched and parsed with `trafilatura`/`BeautifulSoup`. Empty, too-short, or unreadable pages are discarded.
4. **Source classification:** Evidence receives `source_category` and `source_role`, such as `news_outlet`, `primary_official`, `social_post`, `original_post`, `author_interpretation`, or `background_support`.
5. **Semantic ranking:** OpenAI embeddings rank candidate evidence against the post context. Sources found by multiple providers receive provider attribution as a convergence signal.
6. **Claim-source validation:** Each bullet declares a `claim_label`; the validator checks whether the cited source type can support that kind of claim.

The important distinction is:

| Claim type | What it means | Expected citation support |
|---|---|---|
| `confirmed_fact` | The bullet states a factual claim as established | Strong web/news/official/court/fact-check evidence |
| `official_position` | The bullet attributes a position, allegation, or demand to an institution or named actor | Official, primary, court, recognized news, or directly compatible source |
| `author_interpretation` | The bullet explains how the original author frames or argues something | Original post, thread context, or compatible contextual source |
| `public_reaction` | The bullet summarizes replies, reactions, or public response | Thread, social, or reaction-oriented evidence |

This prevents social posts, screenshots, or opinion-heavy context from being promoted into factual proof. They can still be useful, but only for the right kind of claim.

---

## Warnings and Refusal Behavior

Warnings are part of the safety contract, not generic errors. They explain where the evidence is weaker, interpretive, or incompatible with a factual claim.

Examples:

- A social post used as the only support for a factual claim triggers a warning.
- A sensitive factual claim without official, court, fact-checking, or strong news support triggers a warning.
- An image can support what is visible in the image, but cannot independently confirm the factual truth of the text shown in it.
- A post that mostly expresses opinion can still produce useful bullets if they are labeled as `author_interpretation` or `public_reaction`.

When validation fails, the system first attempts one repair pass. The repair prompt asks the model to preserve useful context by reclassifying claims, adding compatible citations, or rewriting claims as attributed context. If the repaired output is still incompatible, unsupported bullets are removed. If fewer than 3 valid bullets remain, the API returns:

```json
{
  "explanation": [],
  "warnings": [
    {
      "code": "CRITICAL_BULLETS_REMOVED",
      "message": "Unsupported bullets were removed because their citations did not match the claim type."
    }
  ]
}
```

That empty explanation is an intentional anti-hallucination outcome: the system refuses to provide a neat but unsupported answer.

---

## Key Design Decisions

### Platform: Bluesky with a platform-agnostic interface

Bluesky was chosen because the assignment PDF uses it as the reference platform, its public AT Protocol API requires no authentication to read posts, and X/Twitter and Reddit restrict API access significantly.

The core agent is platform-agnostic: it receives a normalized `PostData` object from a `PostFetcher` Protocol interface. Adding support for Reddit, blogs, news articles, or RSS feeds requires only a new adapter — the pipeline does not change.

### RAG without a vector database

The pipeline is a retrieval-augmented generation pattern, but does not use a vector store. Evidence is retrieved fresh per request via web search, page content is read and ranked in memory with NumPy cosine similarity, and nothing is persisted between requests. This keeps the system stateless, reproducible, and dependency-free beyond the OpenAI API.

### Separate live and eval flows — no fallback between them

The live mode (`POST /api/explain`) calls Bluesky and a real search provider. If a search provider is not configured, it returns `search_provider_required` rather than degrading silently.

The eval mode (`make eval`) uses pre-cached post and evidence fixtures and does not call Bluesky, Brave, Tavily, or any web page. The only external dependency during eval is the OpenAI API for generation, embeddings, and the LLM-as-judge. Results are reproducible.

Both modes share the same ranking, generation, and citation validation components.

### Evidence-first generation

The model does not receive raw search results and generate freely. It receives normalized post context, parsed page content, ranked evidence, source categories, and source roles. Generation is followed by citation validation and a single repair pass. The intended behavior is conservative: produce a useful cited explanation when the evidence supports it, or return warnings and `explanation: []` when it does not.

### Lightweight internal observability

For a fast PoC, the observability layer was kept internal and simple rather than adding heavy infrastructure. Every request receives an `x-trace-id` header. Every live and eval execution generates a run artifact at `backend/runs/{mode}/{run_id}.json` containing inputs, node durations, retrieved sources, discarded sources, ranking decisions, final response, warnings, and citation repair audit data when a repair pass runs.

The frontend Observability page reads these local artifacts and provides a trace view of the run. The Analysis page aggregates the same artifacts to compare search providers and model stacks. API keys and tokens are redacted before persistence. OpenTelemetry spans are also emitted per node and can be exported via OTLP if a future deployment needs deeper tracing.

### LangGraph as the orchestrator

The pipeline uses a `StateGraph` for explicit state, ordered nodes, tracing hooks per node, and clean separation between live and eval flows. Each node is a small, testable async function with a typed input/output. LangGraph was chosen for its auditability, not for multi-agent capability.

---

## Project Structure

```
contextual-post-explainer/
│
├── README.md
├── docker-compose.yml
├── Makefile
├── .env.example                   # copy to .env and fill in keys
│
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/
│       ├── main.py                # FastAPI app factory
│       ├── config.py              # pydantic-settings, no silent defaults
│       ├── api/                   # routes, error handlers, dependencies
│       ├── application/           # LiveExplanationService, EvalExplanationService
│       ├── graphs/                # LangGraph live_graph, eval_graph, state
│       ├── domain/                # models, policies, validation, deduplication, errors
│       ├── ports/                 # PostFetcher, SearchProvider, LLMClient, etc.
│       ├── adapters/              # Bluesky, Brave, Tavily, Composite, OpenAI, HTTP
│       ├── observability/         # structlog, OTel, run_recorder, redaction
│       ├── eval/                  # runner, metrics, groundedness judge
│       ├── analysis/              # run artifact aggregation for comparison API
│       └── prompts/               # prompts.toml (versioned, hashed in run artifacts)
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── features/
│       │   ├── explainer/         # main UI: URL input, post preview, explanation, sources
│       │   ├── observability/     # run history and artifact viewer
│       │   └── analysis/          # provider and model comparison dashboard
│       └── shared/                # API client, SSE client, shared components
│
└── eval/
    ├── dataset.yaml               # 12 test cases
    └── fixtures/
        ├── posts/                 # pre-cached PostData JSON
        └── evidence/              # pre-cached Evidence JSON
```

---

## Requirements

- Docker, if you want to run the backend and frontend in containers
- Python 3.11+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+
- `OPENAI_API_KEY`
- For live mode: a search provider key (`TAVILY_API_KEY` or `BRAVE_API_KEY`)

---

## Quickstart

### Docker

```bash
git clone <repo-url>
cd contextual-post-explainer

make setup-docker
# Edit .env and fill in OPENAI_API_KEY and TAVILY_API_KEY (or BRAVE_API_KEY)
make up
```

This starts both services:

```text
Frontend: http://localhost:${APP_FRONTEND_PORT:-5173}
Backend:  http://localhost:${APP_BACKEND_PORT:-8000}
```

The backend container mounts `./backend/runs` into `/app/runs`. Existing run artifacts cloned with the repository are available immediately in Observability and Analysis, and new runs generated inside Docker are written back to the local `backend/runs` folder.
The Docker setup/start scripts prepare this folder with write permissions for the backend container.

If these ports are already in use, change `APP_FRONTEND_PORT` and `APP_BACKEND_PORT` in `.env` before running `make up`.

### Without Docker

**Local setup and start:**

```bash
make setup-local
# Edit .env and fill in OPENAI_API_KEY and TAVILY_API_KEY (or BRAVE_API_KEY)
make up
```

This copies missing environment files from the examples and installs backend/frontend dependencies locally.

After either setup path, use the same lifecycle commands:

```bash
make up
make down
```

`make up` and `make down` read `.run/deploy_mode`, which is written by `make setup-local` or `make setup-docker`, and choose the local or Docker flow automatically.

Service URLs:

```text
Frontend: http://localhost:${APP_FRONTEND_PORT:-5173}
Backend:  http://localhost:${APP_BACKEND_PORT:-8000}
```

Local mode writes process logs to `logs/backend.log` and `logs/frontend.log`, with PIDs under `.run/`. Docker mode uses the normal Compose commands, for example `docker compose logs backend` and `docker compose logs frontend`.

Before running live analysis, edit `.env` and fill in at least `OPENAI_API_KEY`, `SEARCH_PROVIDER`, and the matching provider key. If the default ports are occupied, set `APP_BACKEND_PORT` and `APP_FRONTEND_PORT` before running `make up`.

The examples below use the default ports. If you changed them, use the URLs printed by `make up` or Docker Compose.

Foreground commands are still available for development:

```bash
make backend-run
make frontend-run
```

---

## Configuration

Copy `.env.example` to `.env` in the repo root and fill in the values.

```env
# Required for all modes
OPENAI_API_KEY=sk-...
OPENAI_GENERATION_MODEL=gpt-4o
OPENAI_JUDGE_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_VISION_MODEL=gpt-4o

# Host ports used by Docker Compose and local make up
APP_BACKEND_PORT=8000
APP_FRONTEND_PORT=5173
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]

# Required for live mode (pick one or use composite)
SEARCH_PROVIDER=tavily          # brave | tavily | composite
TAVILY_API_KEY=tvly-...
BRAVE_API_KEY=BSA...            # optional if SEARCH_PROVIDER=tavily

# Required for eval mode
EVAL_FIXTURE_DIR=eval/fixtures

# Optional: labels for comparative analysis runs
COMPARISON_GROUP_ID=
COMPARISON_CONFIG_ID=
```

The frontend reads `VITE_API_BASE_URL` from `frontend/.env`. Copy `frontend/.env.example` to `frontend/.env` for manual frontend development. The `make up` flow overrides it automatically from `APP_BACKEND_PORT`.

**Safe evaluator defaults and tested upgrade path:**

| Model | Default | Notes |
|---|---|---|
| Generation | `gpt-4o` | Safe baseline for evaluator access. Upgrade to `gpt-5.1` when the key has access. |
| Judge | `gpt-4o-mini` | Safe baseline. Experiments used `gpt-5-mini` for newer-stack comparison. |
| Embedding | `text-embedding-3-small` | Larger model tested but showed no product improvement |
| Image analysis | `gpt-4o` | Safe baseline. Upgrade to `gpt-5.1` when available. |
| Search | `tavily` | Highest completion reliability; Brave useful in composite mode |

---

## Running the Evaluation Harness

The eval harness requires only `OPENAI_API_KEY`. It does not call Bluesky, Brave, Tavily, or any web page — it uses pre-cached fixtures.

```bash
make eval
```

Results are written to:
- `eval/results/latest.json`
- `eval/results/latest.md`
- `backend/runs/eval/{run_id}.json` (per-case artifact with groundedness detail)

**Test cases (12 total):**

| ID | Type | What it tests |
|---|---|---|
| `tc01_public_launch` | Product announcement | Factual claim with public source |
| `tc02_thread_reply` | Thread reply | Context dependency on parent post |
| `tc03_external_link` | External link | Source fetcher reads linked article |
| `tc04_quote_post` | Quote-post | Context from quoted post |
| `tc05_image_alt` | Image with alt text | Alt text as image evidence |
| `tc06_ambiguous_reference` | Ambiguous phrasing | Evidence narrows interpretation |
| `tc07_factual_claim` | API rate limit claim | Factual verification with primary source |
| `tc08_low_evidence` | Private joke | System returns `[]` instead of inventing |
| `tc09_recent_event` | Public beta | Recent event with indexed context |
| `tc10_multi_reference` | Multiple topics | Separate context for each reference |
| `tc11_groundedness_supported` | Groundedness | Bullet-level verification by judge LLM |
| `tc12_image_text_extraction` | Image OCR | Visible text extracted from image context |

**Note:** For many test cases (e.g., `tc08_low_evidence`), the expected and correct outcome is an empty `explanation` array. This demonstrates the system's commitment to its citation contract, refusing to generate claims when evidence is insufficient or unreliable.

**5 metrics:**

| Metric | Description |
|---|---|
| `fact_coverage` | Deterministic lexical coverage using substring and token overlap between expected facts and generated bullets |
| `citation_coverage` | Fraction of bullets with at least one source ID |
| `hallucination_penalty` | Token overlap between `must_not_claim` list and generated bullets |
| `groundedness` | LLM-as-judge verdict per bullet against its cited sources (`supported` / `partially_supported` / `unsupported`) |
| `usefulness` | Composite score (1–5) derived from the four metrics above |

---

## API Reference

### `GET /api/health`

```json
{
  "status": "ok",
  "service": "contextual-post-explainer-api",
  "version": "0.1.0"
}
```

### `GET /api/config/status`

Returns current model and provider configuration, including live/eval readiness flags. `status` is `ready` when live search is fully configured, `degraded` when the backend can start but live mode is missing provider credentials, and `invalid` when required runtime configuration is missing.

### `POST /api/explain`

**Request:**
```json
{
  "url": "https://bsky.app/profile/user.bsky.social/post/3k...",
  "include_debug": false
}
```

**Success response:**
```json
{
  "post": {
    "url": "...",
    "author": { "handle": "user.bsky.social" },
    "text": "...",
    "platform": "bluesky",
    "images": []
  },
  "explanation": [
    { "text": "...", "source_ids": ["s1", "s2"], "claim_label": "confirmed_fact", "confidence": "high", "warnings": [] }
  ],
  "sources": [
    { "id": "s1", "title": "...", "url": "...", "snippet": "...", "source_type": "web", "source_category": "news_outlet", "source_role": "independent_context" }
  ],
  "confidence": "high",
  "warnings": [],
  "execution_time_ms": 8400
}
```

**Error responses:**

| Error code | HTTP | Meaning |
|---|---|---|
| `search_provider_required` | 400 | Live mode configured without a search provider key |
| `unsupported_platform` | 400 | URL is not a recognized Bluesky post URL |
| `post_not_found` | 404 | Post was deleted or URL is incorrect |
| `external_provider_error` | 502 | Bluesky, search provider, or OpenAI returned an error |

When evidence is insufficient, the response returns HTTP 200 with `explanation: []` and descriptive warnings rather than an error status.

### `POST /api/explain/stream`

Same request body as `/api/explain`. Returns a Server-Sent Events stream with `progress` events during processing and a final `result` event with the full response payload. Each progress event includes a `step` label (`Fetching post`, `Searching context`, `Reading sources`, `Ranking evidence`, `Generating explanation`) and a `status` field.

### `GET /api/runs` and `GET /api/runs/{run_id}`

List and retrieve run artifacts persisted to `backend/runs/`.

### `GET /api/analysis`

Aggregates run artifacts and returns provider and model comparison data: average bullet count, source count, warning count, execution time, and URL-level behavior change detection across different configurations.

---

## Search Providers

Set `SEARCH_PROVIDER` in `.env` to one of:

| Value | Description |
|---|---|
| `tavily` | Tavily Search API. Recommended default — highest completion reliability in controlled experiments (100% across 23 test URLs). |
| `brave` | Brave Search API. Faster and sometimes finds strong official sources. Produced 3 no-explanation outcomes on the same 23 URLs; better as a composite input than a standalone default. |
| `composite` | Both providers in parallel. Results are merged and deduplicated by canonical URL, title, and content hash. Tracking query parameters (`utm_*`, `fbclid`, etc.) are stripped before comparison. Provider attribution is recorded in each source for analysis. |

In `composite` mode, run artifacts include:
- `search_results_by_provider` — result count per provider per run
- `ranked_sources_by_provider` — which sources made it through ranking per provider
- `ranked_multi_provider_source_count` — sources found by more than one provider
- `cited_multi_provider_source_count` — cited sources independently found by both providers

---

## Multi-Provider Comparison

The project includes built-in tooling for comparing configurations:

**Compare search providers manually:**

```bash
# Run the same URL with different providers and compare artifacts
SEARCH_PROVIDER=tavily make backend-run
SEARCH_PROVIDER=brave make backend-run
SEARCH_PROVIDER=composite make backend-run
```

**Run a dry-run comparison matrix:**

```bash
cd backend
uv run python -m app.analysis.runner --matrix search --dry-run
uv run python -m app.analysis.runner --matrix llm --dry-run
```

Remove `--dry-run` to execute real API calls. Results are written to `backend/runs/comparisons/`.

**View aggregated results in the Analysis page** at `http://localhost:5173/analysis` or via `GET /api/analysis`.

Each run artifact records `comparison_group_id`, `comparison_config_id`, the full model stack, and the prompt configuration hash so experiments remain reproducible and attributable.

**Controlled experiment summary (5 runs on 23 Bluesky URLs):**

| Stack | Success rate | Avg bullets | Avg cited sources | Avg time |
|---|---:|---:|---:|---:|
| Tavily + `gpt-5.1` + small embedding | 100% | 4.48 | 4.83 | 30.8s |
| Tavily + `gpt-5.1` + large embedding | 100% | 4.30 | 4.78 | 31.8s |
| Brave + `gpt-5.1` + small embedding | 87% | 4.50* | 5.60* | 25.5s |
| Composite + `gpt-5.1` + large embedding | 91% | 4.52* | 5.67* | 30.5s |
| Composite + `gpt-5-mini` + large embedding | 4% | — | — | — |

*Per-completed-run averages. Success rate counts are: Brave 20/23; Composite 21/23; `gpt-5-mini` 1/23 (structural output failures).

**Recommendation after experiments:** Use `SEARCH_PROVIDER=tavily` with the safe `gpt-4o` default for broad evaluator compatibility. When the key has access to newer models, `gpt-5.1` is the strongest tested generation/vision option. Use `SEARCH_PROVIDER=composite` for deeper analysis when source diversity matters more than maximum completion rate. Do not use `gpt-5-mini` as the generation model until structured-output retry logic is added.

---

## Image Understanding

When `OPENAI_VISION_MODEL` is set, the agent analyzes post images before generating search queries. The analysis extracts:

- **OCR** — text visible in the image
- **Visual description** — what the image shows
- **Image type** — screenshot, photo, chart, meme, etc.

Image evidence is returned separately with `source_type: "image"`. It is used as context for query decomposition and as a citable source for bullets that reference visual content. Factual claims derived from image text still require an external web source; image analysis alone cannot confirm facts independently.

Alt text from the Bluesky post is preserved and included, but the vision model provides additional structured context beyond the alt text.

If `OPENAI_VISION_MODEL` is not set, the pipeline continues without image analysis and the response includes a warning on posts that have images.

---

## What I Would Do With More Time

- **Additional social and content adapters.** Extend the `PostFetcher` interface beyond Bluesky to support Mastodon, Reddit, Hacker News, RSS feeds, and public article URLs. The pipeline already receives normalized `PostData`, so new platforms would mainly require adapter work instead of changes to ranking, generation, or citation validation.
- **Advanced reranking.** The current implementation uses embeddings plus cosine similarity because it is fast, simple, and appropriate for the PoC. With more time, I would evaluate cross-encoder reranking, pairwise reranking, source-quality-aware reranking, and hybrid scoring that combines semantic relevance, source category, publication recency, provider convergence, and citation compatibility.
- **More robust caching and persistence.** Add Redis or another lightweight cache for repeated post fetches, search results, page extraction, embeddings, and image analysis. This would reduce latency and API cost, especially for repeated evaluation runs and experiments.
- **Production-grade background processing.** Move long-running analysis jobs to a worker queue so the API can return a job ID immediately, stream progress reliably, and survive process restarts without losing run state.
- **Expanded evaluation dataset.** Replace the fixture set with a larger human-reviewed dataset of real social posts, including opinion-heavy posts, image-only posts, breaking news, satire, quote-posts, and low-evidence cases.
- **Human feedback loop.** Add reviewer feedback on bullets, source quality, warning accuracy, and citation compatibility, then feed those judgments back into eval cases, prompt improvements, and ranking experiments.
- **Cost and latency optimization.** Track token usage, model latency, provider latency, source-fetch latency, and per-node cost in the run artifacts so model/provider choices can be optimized with hard numbers.
- **Stronger source trust modeling.** Add configurable source reputation rules, domain-level metadata, source freshness policy, and claim-specific evidence requirements without relying on brittle hardcoded domain allowlists.
- **More advanced citation repair.** Improve repair beyond a single retry by separating reclassification, citation replacement, and bullet rewriting into distinct steps with stricter audit output.
- **Deployment hardening.** Add managed secrets, rate limiting, request quotas, persistent artifact storage, CI/CD, container image publishing, and environment-specific configuration for staging/production.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, custom CSS |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Orchestration | LangGraph (StateGraph) |
| LLM | OpenAI Responses API with JSON Schema structured outputs |
| Embeddings | OpenAI `text-embedding-3-small` |
| Image analysis | OpenAI multimodal model via `OPENAI_VISION_MODEL` (optional, separate pipeline step) |
| Search | Brave Search API, Tavily Search API |
| HTML extraction | trafilatura, BeautifulSoup4 |
| HTTP client | httpx (async) with tenacity retry |
| Config | pydantic-settings |
| Observability | structlog, OpenTelemetry SDK |
| Testing | pytest, pytest-asyncio, respx |
| Linting | ruff, mypy |
| Package manager | uv (backend), npm (frontend) |
| Container | Docker Compose |
