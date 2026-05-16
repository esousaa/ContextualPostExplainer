import re
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.config import get_settings
from app.domain.errors import ConfigurationError
from app.observability.logging import configure_logging
from app.observability.tracing import configure_tracing

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Contextual Post Explainer API",
        version="0.1.0",
    )
    register_error_handlers(app)
    app.include_router(router)
    _configure_cors(app)
    configure_tracing(app)

    @app.middleware("http")
    async def bind_trace_id(request: Request, call_next):
        raw_trace = request.headers.get("x-trace-id") or ""
        trace_id = re.sub(r"[^A-Za-z0-9._-]", "", raw_trace)[:64] or uuid4().hex
        bind_contextvars(trace_id=trace_id)
        try:
            response = await call_next(request)
            response.headers["x-trace-id"] = trace_id
            return response
        finally:
            logger.info("request_completed", path=request.url.path, trace_id=trace_id)
            clear_contextvars()

    return app


def _configure_cors(app: FastAPI) -> None:
    try:
        settings = get_settings()
    except ConfigurationError:
        logger.warning("cors_not_configured_invalid_settings")
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app = create_app()
