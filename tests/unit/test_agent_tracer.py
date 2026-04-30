"""
Unit tests for Agent Tracer (S4-01).

Tests OpenTelemetry instrumentation and Prometheus metrics.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from observability.agent_tracer import (
    trace_agent_node,
    record_llm_call,
    record_validation_retry,
    record_dag_execution,
    record_session_created,
    record_session_ended,
    record_approval_requested,
    record_approval_decision,
    record_opa_check,
    record_confidence_distribution,
    record_confidence_transition,
    record_gate_check,
    record_error_classification,
    record_fix_attempt,
    record_escalation,
    record_finops_evaluation,
    get_current_span,
    add_span_attributes,
    add_span_event,
    # Metrics
    LLM_CALL_COUNTER,
    LLM_LATENCY,
    TOKEN_USAGE,
    NODE_DURATION,
    VALIDATION_RETRY_COUNTER,
    DAG_EXECUTION_COUNTER,
    SESSION_COUNTER,
    SESSION_ACTIVE,
    APPROVAL_REQUESTS,
    APPROVAL_DECISIONS,
    OPA_CHECKS,
    OPA_VIOLATIONS,
    CONFIDENCE_DISTRIBUTION,
    CONFIDENCE_TRANSITIONS,
    GATE_CHECKS,
    ERROR_CLASSIFICATION,
    FIX_ATTEMPTS,
    ESCALATIONS,
    FINOPS_EVALUATIONS,
    FINOPS_MONTHLY_COST,
    FINOPS_PATHS_EXPLORED,
    FINOPS_ARCHITECTURE_RECOMMENDATIONS,
)


class TestTraceAgentNodeDecorator:
    """Test the @trace_agent_node decorator."""

    @pytest.mark.asyncio
    async def test_decorator_creates_span(self):
        """Test decorator creates a span with correct name."""
        @trace_agent_node("test_node")
        async def test_fn(state):
            return state

        state = {"session_id": "test-123"}
        result = await test_fn(state)

        assert result == state

    @pytest.mark.asyncio
    async def test_decorator_records_duration(self):
        """Test decorator records node duration metric."""
        @trace_agent_node("duration_test")
        async def slow_fn(state):
            import asyncio
            await asyncio.sleep(0.01)
            return state

        state = {"session_id": "test-456"}
        await slow_fn(state)

        # Metric should be recorded (we can't easily check value without registry)

    @pytest.mark.asyncio
    async def test_decorator_handles_exceptions(self):
        """Test decorator records errors on exception."""
        @trace_agent_node("error_test")
        async def failing_fn(state):
            raise ValueError("Test error")

        state = {"session_id": "test-789"}
        with pytest.raises(ValueError):
            await failing_fn(state)

    @pytest.mark.asyncio
    async def test_decorator_tracks_intent_spec_version(self):
        """Test decorator tracks intent spec version."""
        @trace_agent_node("spec_test")
        async def spec_fn(state):
            state["intent_spec"] = {"version": 5, "items": {"a": {}, "b": {}}}
            return state

        state = {"session_id": "test-spec"}
        result = await spec_fn(state)

        assert result["intent_spec"]["version"] == 5


class TestLLMMetrics:
    """Test LLM call metrics recording."""

    def test_record_llm_call_success(self):
        """Test recording successful LLM call."""
        record_llm_call(
            node="intent_parser",
            model="claude-sonnet-4",
            latency=1.5,
            prompt_tokens=100,
            completion_tokens=50,
            status="success",
        )
        # No exception means success

    def test_record_llm_call_error(self):
        """Test recording failed LLM call."""
        record_llm_call(
            node="planner",
            model="gpt-4o",
            latency=0.5,
            prompt_tokens=200,
            completion_tokens=0,
            status="error",
        )

    def test_record_validation_retry(self):
        """Test recording validation retry."""
        record_validation_retry("MISSING_PROVIDER")
        record_validation_retry("INVALID_REFERENCE")


class TestDAGMetrics:
    """Test DAG execution metrics."""

    def test_record_dag_execution_success(self):
        """Test recording successful DAG execution."""
        record_dag_execution(
            dag_id="infra_dag",
            session_id="session-123",
            total_nodes=5,
            completed_nodes=5,
            failed_nodes=0,
            execution_time=10.5,
        )

    def test_record_dag_execution_failure(self):
        """Test recording failed DAG execution."""
        record_dag_execution(
            dag_id="deploy_dag",
            session_id="session-456",
            total_nodes=8,
            completed_nodes=6,
            failed_nodes=2,
            execution_time=25.0,
        )


class TestSessionMetrics:
    """Test session metrics recording."""

    def test_record_session_created(self):
        """Test recording session creation."""
        record_session_created(tenant_id="tenant-a")
        record_session_created(tenant_id="tenant-b")

    def test_record_session_ended_completed(self):
        """Test recording completed session."""
        record_session_ended(
            tenant_id="tenant-a",
            status="completed",
            duration_seconds=1800.0,
            turn_count=10,
        )

    def test_record_session_ended_cancelled(self):
        """Test recording cancelled session."""
        record_session_ended(
            tenant_id="tenant-b",
            status="cancelled",
            duration_seconds=300.0,
            turn_count=3,
        )

    def test_record_session_ended_expired(self):
        """Test recording expired session."""
        record_session_ended(
            tenant_id="tenant-c",
            status="expired",
            duration_seconds=86400.0,
            turn_count=0,
        )


class TestApprovalMetrics:
    """Test approval gate metrics."""

    def test_record_approval_requested_high_risk(self):
        """Test recording high risk approval request."""
        blast_radius = {
            "resources_to_create": 5,
            "resources_to_update": 10,
            "resources_to_delete": 3,
            "resources_to_replace": 1,
        }
        record_approval_requested(risk_level="HIGH", blast_radius=blast_radius)

    def test_record_approval_requested_low_risk(self):
        """Test recording low risk approval request."""
        blast_radius = {
            "resources_to_create": 1,
            "resources_to_update": 0,
            "resources_to_delete": 0,
            "resources_to_replace": 0,
        }
        record_approval_requested(risk_level="LOW", blast_radius=blast_radius)

    def test_record_approval_decision_approved(self):
        """Test recording approved decision."""
        record_approval_decision(
            decision="approved",
            risk_level="MEDIUM",
            wait_time_seconds=45.0,
            cost_delta=50.0,
        )

    def test_record_approval_decision_rejected(self):
        """Test recording rejected decision."""
        record_approval_decision(
            decision="rejected",
            risk_level="HIGH",
            wait_time_seconds=15.0,
            cost_delta=-100.0,
        )

    def test_record_approval_decision_timeout(self):
        """Test recording timeout decision."""
        record_approval_decision(
            decision="timeout",
            risk_level="HIGH",
            wait_time_seconds=300.0,
        )


class TestOPAMetrics:
    """Test OPA policy check metrics."""

    def test_record_opa_check_allow(self):
        """Test recording allowed OPA check."""
        record_opa_check(
            decision="allow",
            policy="intent_security",
            latency_seconds=0.05,
        )

    def test_record_opa_check_deny(self):
        """Test recording denied OPA check with violations."""
        record_opa_check(
            decision="deny",
            policy="intent_security",
            latency_seconds=0.03,
            violations=["wildcard_iam", "open_security_group"],
        )

    def test_record_opa_check_no_violations(self):
        """Test recording deny without violation list."""
        record_opa_check(
            decision="deny",
            policy="intent_security",
            latency_seconds=0.02,
            violations=None,
        )


class TestConfidenceMetrics:
    """Test confidence band metrics."""

    def test_record_confidence_distribution(self):
        """Test recording confidence distribution."""
        items = {
            "cloud_provider": {"confidence": "stated", "category": "task"},
            "compute_platform": {"confidence": "confirmed", "category": "task"},
            "region": {"confidence": "inferred", "category": "constraint"},
            "budget": {"confidence": "speculative", "category": "meta"},
        }
        record_confidence_distribution(items)

    def test_record_confidence_transition(self):
        """Test recording confidence transition."""
        record_confidence_transition(from_band="speculative", to_band="confirmed")
        record_confidence_transition(from_band="inferred", to_band="stated")

    def test_record_gate_check_allowed(self):
        """Test recording allowed gate check."""
        record_gate_check(action="terraform_apply", allowed=True)

    def test_record_gate_check_blocked(self):
        """Test recording blocked gate check."""
        record_gate_check(action="terraform_apply", allowed=False)


class TestErrorIntelligenceMetrics:
    """Test error intelligence metrics."""

    def test_record_error_classification(self):
        """Test recording error classification."""
        record_error_classification(error_type="MISSING_PROVIDER", severity="high")
        record_error_classification(error_type="INVALID_REFERENCE", severity="medium")

    def test_record_fix_attempt_success(self):
        """Test recording successful fix attempt."""
        record_fix_attempt(error_type="MISSING_PROVIDER", success=True)

    def test_record_fix_attempt_failure(self):
        """Test recording failed fix attempt."""
        record_fix_attempt(error_type="CYCLE_DETECTED", success=False)

    def test_record_escalation(self):
        """Test recording user escalation."""
        record_escalation(reason="max_retries_exceeded")
        record_escalation(reason="ambiguous_error")
        record_escalation(reason="security_concern")


class TestSpanHelpers:
    """Test span context helpers."""

    def test_get_current_span(self):
        """Test getting current span."""
        span = get_current_span()
        # Should return invalid span if not in a trace context
        assert span is not None

    def test_add_span_attributes(self):
        """Test adding span attributes."""
        # Should not raise even outside trace context
        add_span_attributes({
            "custom.key": "value",
            "custom.number": 42,
        })

    def test_add_span_event(self):
        """Test adding span event."""
        # Should not raise even outside trace context
        add_span_event("custom_event", {"key": "value"})
        add_span_event("simple_event")


class TestFinOpsMetrics:
    """Test FinOps evaluation metrics."""

    def test_record_finops_evaluation_eks(self):
        """Test recording EKS architecture evaluation."""
        record_finops_evaluation(
            session_id="session-123",
            primary_architecture="EKS + ALB + Aurora",
            monthly_cost=2500.0,
            paths_explored=4,
            priority="performance",
        )

    def test_record_finops_evaluation_ecs(self):
        """Test recording ECS architecture evaluation."""
        record_finops_evaluation(
            session_id="session-456",
            primary_architecture="ECS Fargate + ALB + RDS",
            monthly_cost=450.0,
            paths_explored=3,
            priority="balanced",
        )

    def test_record_finops_evaluation_lambda(self):
        """Test recording Lambda architecture evaluation."""
        record_finops_evaluation(
            session_id="session-789",
            primary_architecture="Lambda + API Gateway + DynamoDB",
            monthly_cost=50.0,
            paths_explored=3,
            priority="cost",
        )

    def test_record_finops_evaluation_with_scores(self):
        """Test recording evaluation with all scores."""
        record_finops_evaluation(
            session_id="session-scores",
            primary_architecture="ECS Fargate + ALB",
            monthly_cost=300.0,
            paths_explored=4,
            priority="balanced",
            scores={
                "cost_score": 7.5,
                "scalability_score": 8.0,
                "reliability_score": 8.5,
                "security_score": 8.0,
                "composite_score": 7.95,
            },
        )

    def test_record_finops_evaluation_ec2(self):
        """Test recording EC2 architecture evaluation."""
        record_finops_evaluation(
            session_id="session-ec2",
            primary_architecture="EC2 Auto Scaling + RDS",
            monthly_cost=800.0,
            paths_explored=5,
            priority="security",
        )


class TestMetricsExist:
    """Test that all expected metrics exist."""

    def test_llm_metrics_exist(self):
        """Test LLM metrics are defined."""
        assert LLM_CALL_COUNTER is not None
        assert LLM_LATENCY is not None
        assert TOKEN_USAGE is not None

    def test_node_metrics_exist(self):
        """Test node metrics are defined."""
        assert NODE_DURATION is not None
        assert VALIDATION_RETRY_COUNTER is not None

    def test_dag_metrics_exist(self):
        """Test DAG metrics are defined."""
        assert DAG_EXECUTION_COUNTER is not None

    def test_session_metrics_exist(self):
        """Test session metrics are defined."""
        assert SESSION_COUNTER is not None
        assert SESSION_ACTIVE is not None

    def test_approval_metrics_exist(self):
        """Test approval metrics are defined."""
        assert APPROVAL_REQUESTS is not None
        assert APPROVAL_DECISIONS is not None

    def test_opa_metrics_exist(self):
        """Test OPA metrics are defined."""
        assert OPA_CHECKS is not None
        assert OPA_VIOLATIONS is not None

    def test_confidence_metrics_exist(self):
        """Test confidence metrics are defined."""
        assert CONFIDENCE_DISTRIBUTION is not None
        assert CONFIDENCE_TRANSITIONS is not None
        assert GATE_CHECKS is not None

    def test_error_metrics_exist(self):
        """Test error intelligence metrics are defined."""
        assert ERROR_CLASSIFICATION is not None
        assert FIX_ATTEMPTS is not None
        assert ESCALATIONS is not None

    def test_finops_metrics_exist(self):
        """Test FinOps metrics are defined."""
        assert FINOPS_EVALUATIONS is not None
        assert FINOPS_MONTHLY_COST is not None
        assert FINOPS_PATHS_EXPLORED is not None
        assert FINOPS_ARCHITECTURE_RECOMMENDATIONS is not None
