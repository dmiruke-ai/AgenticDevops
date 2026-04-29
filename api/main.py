"""
FastAPI Application - AI DevOps Agent Platform.

Exposes REST API for session management, turn-based conversations,
and artifact generation.
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentation
from pydantic import BaseModel

from agents.intent_parser.dialogue_policy import DialogueAction, create_dialogue_policy
from agents.intent_parser.semantic_extractor import create_extractor
from config import config
from intent.conflict_detector import ConflictDetector
from intent.confidence import IntentTransitionEngine
from intent.state_store import create_state_store

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

# Initialize components
state_store = None
semantic_extractor = None
dialogue_policy = None
conflict_detector = None
transition_engine = None


@app.on_event("startup")
async def startup():
    """Initialize components on startup."""
    global state_store, semantic_extractor, dialogue_policy, conflict_detector, transition_engine
    state_store = await create_state_store()
    semantic_extractor = create_extractor()
    dialogue_policy = create_dialogue_policy()
    conflict_detector = ConflictDetector()
    transition_engine = IntentTransitionEngine()


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    if state_store:
        await state_store.close()


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
    redis_ok = await state_store.redis.ping() if state_store else False
    return {
        "api": "ok",
        "redis": "ok" if redis_ok else "error",
        "opa": "ok",  # TODO: Check OPA connection
    }


# Request/Response models
class CreateSessionRequest(BaseModel):
    user_id: str | None = None


class SubmitTurnRequest(BaseModel):
    message: str
    conversation_history: list[str] = []


class TurnResponse(BaseModel):
    turn: int
    session_id: str
    response: str
    intent_spec_version: int
    ready_to_execute: bool = False


# Session endpoints
@app.post("/sessions", status_code=201)
async def create_session(request: CreateSessionRequest = None):
    """Create a new conversation session."""
    user_id = request.user_id if request else None
    session_id = await state_store.create_session(user_id=user_id)
    metadata = await state_store.get_metadata(session_id)

    return JSONResponse(
        content={
            "session_id": session_id,
            "created_at": metadata["created_at"],
            "status": "active",
        },
        status_code=201,
    )


@app.post("/sessions/{session_id}/turns")
async def submit_turn(session_id: str, request: SubmitTurnRequest) -> TurnResponse:
    """
    Submit a user message turn.

    Process:
    1. Retrieve existing IntentSpec
    2. Extract intent from user message (Semantic Extractor)
    3. Detect conflicts (ConflictDetector)
    4. Merge extraction into IntentSpec
    5. Generate dialogue response (Dialogue Policy)
    6. Save updated IntentSpec
    """
    # Check session exists
    if not await state_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Get existing spec
    spec = await state_store.get_spec(session_id)
    metadata = await state_store.get_metadata(session_id)
    turn = metadata.get("turn_count", 0) + 1

    # Extract intent
    extraction = await semantic_extractor.extract(
        user_message=request.message,
        existing_spec=spec,
        conversation_history=request.conversation_history,
        turn=turn,
    )

    # Detect conflicts with new items
    conflicts = conflict_detector.detect(spec, extraction.new_items)

    # Merge new items into spec
    for item in extraction.new_items:
        spec.items[item.id] = item

    # Update spec metadata
    spec.version += 1
    spec.open_questions = extraction.open_questions
    spec.conflicts.extend(conflicts)

    # Save updated spec
    await state_store.save_spec(spec)

    # Update turn count
    metadata["turn_count"] = turn
    await state_store.redis.set(
        f"session:{session_id}:metadata",
        json.dumps(metadata),
        ex=config.intent_spec_ttl_seconds,
    )

    # Generate dialogue response
    action = DialogueAction.ASK if spec.open_questions else DialogueAction.REFLECT
    if conflicts:
        action = DialogueAction.ASK  # Resolve conflicts first

    dialogue_response = await dialogue_policy.generate_response(
        intent_spec=spec,
        open_questions=spec.open_questions,
        conflicts=conflicts,
        action=action,
    )

    return TurnResponse(
        turn=turn,
        session_id=session_id,
        response=dialogue_response.response_text,
        intent_spec_version=spec.version,
        ready_to_execute=dialogue_response.ready_to_execute,
    )


@app.get("/sessions/{session_id}/intent")
async def get_intent_spec(session_id: str):
    """Retrieve current IntentSpec for session."""
    spec = await state_store.get_spec(session_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Session not found")

    return spec.model_dump()


@app.get("/sessions/{session_id}/metadata")
async def get_session_metadata(session_id: str):
    """Get session metadata."""
    metadata = await state_store.get_metadata(session_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Session not found")

    return metadata


@app.post("/sessions/{session_id}/approve")
async def approve_deployment(session_id: str):
    """Approve a deployment action."""
    # TODO: Implement approval gate logic in Sprint 4
    return {
        "session_id": session_id,
        "approved": True,
        "status": "stub - approval gate not yet implemented",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
