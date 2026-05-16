# Contextual Post Explainer Frontend

React frontend for the FastAPI backend.

## Setup

From the repository root, choose one setup mode:

```bash
make setup-docker
# or
make setup-local
```

After setup, use `make up` to start both services and `make down` to stop them. The selected mode is saved in `.run/deploy_mode`.

The local ports are configured in the root `.env`:

```env
APP_BACKEND_PORT=8000
APP_FRONTEND_PORT=5173
```

To work only on the frontend:

```bash
npm install
cp .env.example .env
npm run dev
```

The app reads the backend URL from `VITE_API_BASE_URL`. The `make up` flow injects this value from `APP_BACKEND_PORT`; manual edits are only needed for standalone frontend development.

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
