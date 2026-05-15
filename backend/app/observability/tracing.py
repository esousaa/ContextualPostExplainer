from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_CONFIGURED = False


def configure_tracing(app: FastAPI) -> None:
    global _CONFIGURED
    if not _CONFIGURED:
        provider = TracerProvider(
            resource=Resource.create({"service.name": "contextual-post-explainer-backend"})
        )
        trace.set_tracer_provider(provider)
        HTTPXClientInstrumentor().instrument()
        _CONFIGURED = True

    FastAPIInstrumentor.instrument_app(app)


def get_tracer():
    return trace.get_tracer("contextual-post-explainer")
