.PHONY: setup-local setup-docker deploy-start up down backend-run backend-test backend-lint backend-format frontend-run frontend-test frontend-lint frontend-build eval

setup-local:
	./scripts/setup-local.sh

setup-docker:
	./scripts/setup-docker.sh

deploy-start: setup-local up

up:
	./scripts/app-up.sh

down:
	./scripts/app-down.sh

backend-run:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

backend-test:
	cd backend && uv run pytest

backend-lint:
	cd backend && uv run ruff check .

backend-format:
	cd backend && uv run ruff format .

eval:
	cd backend && uv run python -m app.eval.runner --dataset ../eval/dataset.yaml

frontend-run:
	cd frontend && npm run dev

frontend-test:
	cd frontend && npm run test

frontend-lint:
	cd frontend && npm run lint

frontend-build:
	cd frontend && npm run build
