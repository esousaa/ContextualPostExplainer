# Contextual Post Explainer Frontend

React frontend for the FastAPI backend.

## Setup

```bash
npm install
npm run dev
```

The app reads the backend URL from `VITE_API_BASE_URL`.

```bash
cp .env.example .env
```

Default:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Commands

```bash
npm run dev
npm run build
npm run test
npm run lint
```

## Backend

Run the backend from the repository root:

```bash
make backend-run
```

The frontend calls only the FastAPI backend. It does not call OpenAI,
Bluesky, Tavily, Brave, or any other provider directly.
