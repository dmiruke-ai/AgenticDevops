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
