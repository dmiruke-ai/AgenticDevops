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


@app.post("/sessions/{session_id}/output")
async def generate_artifacts(session_id: str, output_mode: str = "artifacts"):
    """
    Generate infrastructure artifacts from confirmed IntentSpec.

    This is the synchronous version that returns all artifacts at once.
    For streaming progress updates, use /sessions/{session_id}/output/stream.

    Args:
        session_id: Session identifier
        output_mode: Output mode (design/artifacts/deploy)

    Returns:
        Generated artifacts (Terraform, IAM, CI/CD)
    """
    from execution.output_router import create_output_router
    from execution.executor import DAGExecutor
    from agents.generators import (
        create_terraform_generator,
        create_iam_generator,
        create_pipeline_generator,
    )
    from agents.finops import create_finops_scorer

    # Check session exists
    if not await state_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Get confirmed IntentSpec
    spec = await state_store.get_spec(session_id)

    # Route to appropriate DAG
    router = create_output_router()
    try:
        dag = router.route(spec, mode=output_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create agent registry
    agents = {
        "finops_score": create_finops_scorer(),
        "infra_gen": create_terraform_generator(),
        "iam_gen": create_iam_generator(),
        "pipeline_gen": create_pipeline_generator(),
    }

    # Execute DAG
    executor = DAGExecutor(agents=agents)
    result = await executor.execute(dag, initial_context={"intent_spec": spec})

    return {
        "session_id": session_id,
        "output_mode": output_mode,
        "status": "success" if result.all_succeeded() else "partial_failure",
        "artifacts": result.final_context,
        "execution_time_seconds": result.total_duration_seconds,
    }


@app.get("/sessions/{session_id}/output/stream")
async def stream_artifact_generation(session_id: str, output_mode: str = "artifacts"):
    """
    Stream artifact generation progress using Server-Sent Events (SSE).

    Streams progress updates as each DAG node completes:
    - Node start events
    - Node completion events with outputs
    - Error events
    - Final completion event

    Example:
        GET /sessions/{id}/output/stream?output_mode=artifacts

    Response format (text/event-stream):
        event: node_start
        data: {"node_id": "finops_score", "status": "running"}

        event: node_complete
        data: {"node_id": "finops_score", "output": {...}, "duration": 2.5}

        event: complete
        data: {"status": "success", "total_duration": 45.2}
    """
    from fastapi.responses import StreamingResponse
    from execution.output_router import create_output_router
    from execution.executor import DAGExecutor
    from agents.generators import (
        create_terraform_generator,
        create_iam_generator,
        create_pipeline_generator,
    )
    from agents.finops import create_finops_scorer
    import asyncio
    import time

    # Check session exists
    if not await state_store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # Get confirmed IntentSpec
    spec = await state_store.get_spec(session_id)

    # Route to appropriate DAG
    router = create_output_router()
    try:
        dag = router.route(spec, mode=output_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create agent registry
    agents = {
        "finops_score": create_finops_scorer(),
        "infra_gen": create_terraform_generator(),
        "iam_gen": create_iam_generator(),
        "pipeline_gen": create_pipeline_generator(),
    }

    async def event_generator():
        """Generate SSE events as DAG executes."""
        try:
            # Send start event
            yield f"event: start\\ndata: {json.dumps({'session_id': session_id, 'output_mode': output_mode})}\\n\\n"

            executor = DAGExecutor(agents=agents)
            start_time = time.time()

            # Execute DAG
            result = await executor.execute(dag, initial_context={"intent_spec": spec})

            # Send node completion events
            for node_id, node in dag.nodes.items():
                node_output = result.final_context.get(f"{node_id}_output", {})
                event_data = {
                    "node_id": node_id,
                    "status": node.status.value,
                    "output_keys": list(node_output.keys()) if isinstance(node_output, dict) else [],
                }
                yield f"event: node_complete\\ndata: {json.dumps(event_data)}\\n\\n"
                await asyncio.sleep(0.1)  # Small delay for client buffering

            # Send completion event
            completion_data = {
                "status": "success" if result.all_succeeded() else "partial_failure",
                "total_duration": time.time() - start_time,
                "completed_nodes": len([n for n in dag.nodes.values() if n.status.value == "completed"]),
                "failed_nodes": len([n for n in dag.nodes.values() if n.status.value == "failed"]),
            }
            yield f"event: complete\\ndata: {json.dumps(completion_data)}\\n\\n"

        except Exception as e:
            # Send error event
            error_data = {"error": str(e), "type": type(e).__name__}
            yield f"event: error\\ndata: {json.dumps(error_data)}\\n\\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
