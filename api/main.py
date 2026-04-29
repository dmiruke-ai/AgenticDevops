"""
FastAPI Application - AI DevOps Agent Platform.

Exposes REST API for session management, turn-based conversations,
and artifact generation.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentation

from config import config

# Create FastAPI app
app = FastAPI(
    title="AI DevOps Agent Platform",
    description="Intent-driven infrastructure generation with LangGraph multi-agent orchestration",
    version="0.1.0",
)

# Instrument with OpenTelemetry
FastAPIInstrumentation().instrument_app(app)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "ai-devops-agent",
        "version": "0.1.0",
        "status": "healthy",
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "api": "ok",
        "redis": "ok",  # TODO: Check Redis connection
        "opa": "ok",    # TODO: Check OPA connection
    }


# Session endpoints (STUB - to be implemented in Sprint 1)
@app.post("/sessions")
async def create_session():
    """Create a new conversation session."""
    return JSONResponse(
        content={
            "session_id": "stub-session-id",
            "created_at": "2026-04-29T00:00:00Z",
            "status": "active",
        },
        status_code=201,
    )


@app.post("/sessions/{session_id}/turns")
async def submit_turn(session_id: str):
    """Submit a user message turn."""
    return {
        "turn": 1,
        "session_id": session_id,
        "response": "STUB: Intent parser not yet implemented",
    }


@app.get("/sessions/{session_id}/intent")
async def get_intent_spec(session_id: str):
    """Retrieve current IntentSpec for session."""
    return {
        "session_id": session_id,
        "version": 1,
        "items": {},
        "status": "stub",
    }


@app.post("/sessions/{session_id}/approve")
async def approve_deployment(session_id: str):
    """Approve a deployment action."""
    return {
        "session_id": session_id,
        "approved": True,
        "status": "stub",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
