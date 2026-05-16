FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

RUN addgroup --system app && adduser --system --ingroup app app && \
    chown -R app:app /app
USER app

EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
