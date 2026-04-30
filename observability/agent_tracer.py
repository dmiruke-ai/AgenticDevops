"""
Agent Observability Layer - OpenTelemetry instrumentation.

Instruments every LangGraph node with tracing and metrics.
Makes the agent itself debuggable in production.
"""

import functools
import time
from typing import Any, Awaitable, Callable, TypeVar

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from prometheus_client import Counter, Gauge, Histogram

from config import config

# Initialize OpenTelemetry tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer("devops_agent")

# Configure OTLP exporter for Jaeger
otlp_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus Metrics
LLM_CALL_COUNTER = Counter(
    "devops_agent_llm_calls_total",
    "Total LLM API calls",
    ["node", "model", "status"],
)

LLM_LATENCY = Histogram(
    "devops_agent_llm_latency_seconds",
    "LLM call latency by node",
    ["node", "model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

TOKEN_USAGE = Counter(
    "devops_agent_tokens_total",
    "Total tokens consumed",
    ["node", "model", "direction"],  # direction: "prompt" | "completion"
)

INTENT_SPEC_VERSION = Gauge(
    "devops_agent_intent_spec_version",
    "Current IntentSpec version (mutation count) per session",
    ["session_id"],
)

VALIDATION_RETRY_COUNTER = Counter(
    "devops_agent_validation_retries_total",
    "Validation loop retries by error type",
    ["error_type"],
)

NODE_DURATION = Histogram(
    "devops_agent_node_duration_seconds",
    "Node execution duration",
    ["node", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)


AgentState = dict[str, Any]
F = TypeVar("F", bound=Callable[..., Awaitable[AgentState]])


def trace_agent_node(node_name: str) -> Callable[[F], F]:
    """
    Decorator for LangGraph nodes. Captures:
    - Node execution duration
    - LLM call count within node
    - Token usage (prompt + completion)
    - IntentSpec mutation count
    - Confidence score distribution
    - Retry count
    - Error type if raised

    Usage:
        @trace_agent_node("intent_parser")
        async def intent_parser_node(state: AgentState) -> AgentState:
            ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(state: AgentState) -> AgentState:
            with tracer.start_as_current_span(f"agent.node.{node_name}") as span:
                # Set span attributes
                span.set_attribute("session.id", state.get("session_id", "unknown"))
                span.set_attribute("node.name", node_name)
                span.set_attribute("retry.count", state.get("retry_count", 0))

                start = time.perf_counter()
                status = "success"

                try:
                    result = await fn(state)

                    # Record success metrics
                    span.set_attribute("node.status", "success")

                    # Track IntentSpec version if present
                    if "intent_spec" in result:
                        items_count = len(result["intent_spec"].get("items", {}))
                        spec_version = result["intent_spec"].get("version", 0)
                        span.set_attribute("intent_spec.items_count", items_count)
                        span.set_attribute("intent_spec.version", spec_version)

                        session_id = result.get("session_id", "unknown")
                        INTENT_SPEC_VERSION.labels(session_id=session_id).set(spec_version)

                    return result

                except Exception as e:
                    status = "error"
                    span.set_attribute("node.status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.record_exception(e)
                    raise

                finally:
                    duration = time.perf_counter() - start
                    span.set_attribute("duration_ms", duration * 1000)

                    # Record duration metric
                    NODE_DURATION.labels(node=node_name, status=status).observe(duration)

        return wrapper  # type: ignore

    return decorator


def record_llm_call(
    node: str,
    model: str,
    latency: float,
    prompt_tokens: int,
    completion_tokens: int,
    status: str = "success",
) -> None:
    """
    Record metrics for an LLM API call.

    Args:
        node: Name of the node making the call
        model: Model identifier (e.g., "claude-sonnet-4")
        latency: Call duration in seconds
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        status: Call status ("success" or "error")
    """
    LLM_CALL_COUNTER.labels(node=node, model=model, status=status).inc()
    LLM_LATENCY.labels(node=node, model=model).observe(latency)
    TOKEN_USAGE.labels(node=node, model=model, direction="prompt").inc(prompt_tokens)
    TOKEN_USAGE.labels(node=node, model=model, direction="completion").inc(completion_tokens)


def record_validation_retry(error_type: str) -> None:
    """Record a validation retry for a specific error type."""
    VALIDATION_RETRY_COUNTER.labels(error_type=error_type).inc()


# DAG Execution Metrics
DAG_EXECUTION_COUNTER = Counter(
    "devops_agent_dag_executions_total",
    "Total DAG executions",
    ["dag_id", "session_id", "status"],
)

DAG_EXECUTION_TIME = Histogram(
    "devops_agent_dag_execution_seconds",
    "DAG execution time",
    ["dag_id"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

DAG_NODE_COUNT = Histogram(
    "devops_agent_dag_nodes",
    "Number of nodes in DAG",
    ["dag_id"],
    buckets=[1, 3, 5, 10, 20, 50],
)


def record_dag_execution(
    dag_id: str,
    session_id: str,
    total_nodes: int,
    completed_nodes: int,
    failed_nodes: int,
    execution_time: float,
) -> None:
    """
    Record metrics for DAG execution.

    Args:
        dag_id: DAG identifier
        session_id: Session identifier
        total_nodes: Total number of nodes
        completed_nodes: Number of successfully completed nodes
        failed_nodes: Number of failed nodes
        execution_time: Execution time in seconds
    """
    status = "success" if failed_nodes == 0 else "failure"
    DAG_EXECUTION_COUNTER.labels(
        dag_id=dag_id, session_id=session_id, status=status
    ).inc()
    DAG_EXECUTION_TIME.labels(dag_id=dag_id).observe(execution_time)
    DAG_NODE_COUNT.labels(dag_id=dag_id).observe(total_nodes)


# =============================================================================
# Session Metrics (S4-03)
# =============================================================================

SESSION_COUNTER = Counter(
    "devops_agent_sessions_total",
    "Total sessions created",
    ["tenant_id", "status"],
)

SESSION_ACTIVE = Gauge(
    "devops_agent_sessions_active",
    "Currently active sessions per tenant",
    ["tenant_id"],
)

SESSION_DURATION = Histogram(
    "devops_agent_session_duration_seconds",
    "Session duration from creation to completion",
    ["tenant_id", "status"],
    buckets=[60, 300, 600, 1800, 3600, 7200],
)

SESSION_TURNS = Histogram(
    "devops_agent_session_turns",
    "Number of conversation turns per session",
    ["tenant_id"],
    buckets=[1, 2, 5, 10, 20, 50],
)


def record_session_created(tenant_id: str) -> None:
    """Record a new session creation."""
    SESSION_COUNTER.labels(tenant_id=tenant_id, status="created").inc()
    SESSION_ACTIVE.labels(tenant_id=tenant_id).inc()


def record_session_ended(
    tenant_id: str,
    status: str,
    duration_seconds: float,
    turn_count: int,
) -> None:
    """
    Record session completion.

    Args:
        tenant_id: Tenant identifier
        status: Final status (completed, cancelled, expired)
        duration_seconds: Session duration in seconds
        turn_count: Number of conversation turns
    """
    SESSION_COUNTER.labels(tenant_id=tenant_id, status=status).inc()
    SESSION_ACTIVE.labels(tenant_id=tenant_id).dec()
    SESSION_DURATION.labels(tenant_id=tenant_id, status=status).observe(duration_seconds)
    SESSION_TURNS.labels(tenant_id=tenant_id).observe(turn_count)


# =============================================================================
# Approval Gate Metrics (S4-02)
# =============================================================================

APPROVAL_REQUESTS = Counter(
    "devops_agent_approval_requests_total",
    "Total approval requests",
    ["risk_level"],
)

APPROVAL_DECISIONS = Counter(
    "devops_agent_approval_decisions_total",
    "Approval decisions by outcome",
    ["decision", "risk_level"],  # decision: approved, rejected, timeout
)

APPROVAL_WAIT_TIME = Histogram(
    "devops_agent_approval_wait_seconds",
    "Time waiting for approval decision",
    ["decision"],
    buckets=[5, 15, 30, 60, 120, 300],
)

BLAST_RADIUS_RESOURCES = Histogram(
    "devops_agent_blast_radius_resources",
    "Number of resources affected by terraform changes",
    ["action"],  # action: create, update, delete, replace
    buckets=[1, 5, 10, 25, 50, 100],
)

COST_DELTA = Histogram(
    "devops_agent_cost_delta_monthly",
    "Monthly cost change in USD",
    ["direction"],  # direction: increase, decrease
    buckets=[10, 50, 100, 500, 1000, 5000],
)


# =============================================================================
# FinOps Metrics (Tree-of-Thought Architecture Evaluation)
# =============================================================================

FINOPS_EVALUATIONS = Counter(
    "devops_agent_finops_evaluations_total",
    "Total FinOps architecture evaluations",
    ["primary_architecture", "priority"],
)

FINOPS_MONTHLY_COST = Histogram(
    "devops_agent_finops_monthly_cost_usd",
    "Recommended monthly cost in USD",
    ["architecture"],
    buckets=[25, 50, 100, 200, 500, 1000, 2500, 5000],
)

FINOPS_PATHS_EXPLORED = Histogram(
    "devops_agent_finops_paths_explored",
    "Number of architectural paths explored per evaluation",
    buckets=[1, 2, 3, 4, 5, 6, 7, 8],
)

FINOPS_SCORE_DISTRIBUTION = Histogram(
    "devops_agent_finops_score",
    "FinOps score distribution by dimension",
    ["dimension"],  # cost, scalability, reliability, security, composite
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
)

FINOPS_ARCHITECTURE_RECOMMENDATIONS = Counter(
    "devops_agent_finops_recommendations_total",
    "Architecture recommendations by type",
    ["architecture"],  # EKS, ECS, Lambda, EC2, etc.
)


def record_finops_evaluation(
    session_id: str,
    primary_architecture: str,
    monthly_cost: float,
    paths_explored: int,
    priority: str = "balanced",
    scores: dict | None = None,
) -> None:
    """
    Record FinOps evaluation metrics.

    Args:
        session_id: Session identifier
        primary_architecture: Recommended architecture name
        monthly_cost: Estimated monthly cost in USD
        paths_explored: Number of paths evaluated
        priority: User priority (cost, performance, security, balanced)
        scores: Optional dict with cost_score, scalability_score, etc.
    """
    # Normalize architecture name for metrics
    arch_normalized = primary_architecture.split("+")[0].strip().upper()
    if "EKS" in arch_normalized:
        arch_normalized = "EKS"
    elif "ECS" in arch_normalized:
        arch_normalized = "ECS"
    elif "LAMBDA" in arch_normalized:
        arch_normalized = "LAMBDA"
    elif "EC2" in arch_normalized:
        arch_normalized = "EC2"

    FINOPS_EVALUATIONS.labels(
        primary_architecture=arch_normalized,
        priority=priority,
    ).inc()

    FINOPS_MONTHLY_COST.labels(architecture=arch_normalized).observe(monthly_cost)
    FINOPS_PATHS_EXPLORED.observe(paths_explored)
    FINOPS_ARCHITECTURE_RECOMMENDATIONS.labels(architecture=arch_normalized).inc()

    # Record individual scores if provided
    if scores:
        for dimension in ["cost", "scalability", "reliability", "security", "composite"]:
            score = scores.get(f"{dimension}_score", scores.get(dimension))
            if score is not None:
                FINOPS_SCORE_DISTRIBUTION.labels(dimension=dimension).observe(score)


def record_approval_requested(risk_level: str, blast_radius: dict) -> None:
    """
    Record an approval request.

    Args:
        risk_level: Risk level (HIGH, MEDIUM, LOW, NONE)
        blast_radius: Blast radius dict with resource counts
    """
    APPROVAL_REQUESTS.labels(risk_level=risk_level).inc()

    # Record blast radius distribution
    for action in ["create", "update", "delete", "replace"]:
        count = blast_radius.get(f"resources_to_{action}", 0)
        if count > 0:
            BLAST_RADIUS_RESOURCES.labels(action=action).observe(count)


def record_approval_decision(
    decision: str,
    risk_level: str,
    wait_time_seconds: float,
    cost_delta: float = 0.0,
) -> None:
    """
    Record an approval decision.

    Args:
        decision: Decision outcome (approved, rejected, timeout)
        risk_level: Risk level of the request
        wait_time_seconds: Time spent waiting for decision
        cost_delta: Monthly cost change in USD
    """
    APPROVAL_DECISIONS.labels(decision=decision, risk_level=risk_level).inc()
    APPROVAL_WAIT_TIME.labels(decision=decision).observe(wait_time_seconds)

    if cost_delta != 0:
        direction = "increase" if cost_delta > 0 else "decrease"
        COST_DELTA.labels(direction=direction).observe(abs(cost_delta))


# =============================================================================
# OPA Policy Check Metrics (S4-01)
# =============================================================================

OPA_CHECKS = Counter(
    "devops_agent_opa_checks_total",
    "Total OPA policy checks",
    ["decision", "policy"],  # decision: allow, deny
)

OPA_CHECK_LATENCY = Histogram(
    "devops_agent_opa_check_latency_seconds",
    "OPA policy check latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

OPA_VIOLATIONS = Counter(
    "devops_agent_opa_violations_total",
    "OPA policy violations by type",
    ["violation_type"],
)


def record_opa_check(
    decision: str,
    policy: str,
    latency_seconds: float,
    violations: list[str] | None = None,
) -> None:
    """
    Record an OPA policy check.

    Args:
        decision: Decision (allow, deny)
        policy: Policy name
        latency_seconds: Check latency in seconds
        violations: List of violation types if denied
    """
    OPA_CHECKS.labels(decision=decision, policy=policy).inc()
    OPA_CHECK_LATENCY.observe(latency_seconds)

    if violations:
        for violation in violations:
            OPA_VIOLATIONS.labels(violation_type=violation).inc()


# =============================================================================
# Confidence Band Metrics (S4-01)
# =============================================================================

CONFIDENCE_DISTRIBUTION = Counter(
    "devops_agent_confidence_distribution_total",
    "Distribution of confidence bands across spec items",
    ["band", "category"],  # band: speculative, inferred, confirmed, stated
)

CONFIDENCE_TRANSITIONS = Counter(
    "devops_agent_confidence_transitions_total",
    "Confidence band transitions",
    ["from_band", "to_band"],
)

GATE_CHECKS = Counter(
    "devops_agent_gate_checks_total",
    "Gate checks for irreversible actions",
    ["action", "result"],  # result: allowed, blocked
)


def record_confidence_distribution(items: dict) -> None:
    """
    Record confidence band distribution for current spec.

    Args:
        items: Dict of SpecItems with confidence bands
    """
    for key, item in items.items():
        band = item.get("confidence", "speculative")
        category = item.get("category", "task")
        CONFIDENCE_DISTRIBUTION.labels(band=band, category=category).inc()


def record_confidence_transition(from_band: str, to_band: str) -> None:
    """Record a confidence band transition."""
    CONFIDENCE_TRANSITIONS.labels(from_band=from_band, to_band=to_band).inc()


def record_gate_check(action: str, allowed: bool) -> None:
    """
    Record a gate check for an irreversible action.

    Args:
        action: The action being checked
        allowed: Whether the action was allowed
    """
    result = "allowed" if allowed else "blocked"
    GATE_CHECKS.labels(action=action, result=result).inc()


# =============================================================================
# Error Intelligence Metrics (S4-01)
# =============================================================================

ERROR_CLASSIFICATION = Counter(
    "devops_agent_error_classifications_total",
    "Terraform errors by classification",
    ["error_type", "severity"],
)

FIX_ATTEMPTS = Counter(
    "devops_agent_fix_attempts_total",
    "Fix attempts by error type and outcome",
    ["error_type", "outcome"],  # outcome: success, failure
)

ESCALATIONS = Counter(
    "devops_agent_escalations_total",
    "User escalations by reason",
    ["reason"],
)


def record_error_classification(error_type: str, severity: str) -> None:
    """Record an error classification."""
    ERROR_CLASSIFICATION.labels(error_type=error_type, severity=severity).inc()


def record_fix_attempt(error_type: str, success: bool) -> None:
    """Record a fix attempt outcome."""
    outcome = "success" if success else "failure"
    FIX_ATTEMPTS.labels(error_type=error_type, outcome=outcome).inc()


def record_escalation(reason: str) -> None:
    """Record a user escalation."""
    ESCALATIONS.labels(reason=reason).inc()


# =============================================================================
# Span Context Helpers
# =============================================================================

def get_current_span():
    """Get the current active span."""
    return trace.get_current_span()


def add_span_attributes(attributes: dict) -> None:
    """Add attributes to the current span."""
    span = get_current_span()
    if span:
        for key, value in attributes.items():
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict | None = None) -> None:
    """Add an event to the current span."""
    span = get_current_span()
    if span:
        span.add_event(name, attributes=attributes or {})
