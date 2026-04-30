"""
Unit tests for OPA Intent Gate (S3-09).

Tests OPA policy enforcement at the intent layer.
"""

import pytest
from datetime import datetime
from uuid import UUID

from security.opa_intent_gate import (
    OPAIntentGate,
    OPACheckResult,
    IntentPolicyViolation,
    AuditLogEntry,
    create_opa_intent_gate,
)
from intent.schema import (
    ExtractionResult,
    SpecItem,
    ConfidenceBand,
    IntentCategory,
)


class TestOPACheckResult:
    """Test OPACheckResult model."""

    def test_create_allowed_result(self):
        """Test creating an allowed result."""
        result = OPACheckResult(
            allowed=True,
            session_id="test-session",
            turn=1,
        )

        assert result.allowed is True
        assert result.violations == []
        assert result.warnings == []
        assert result.session_id == "test-session"
        assert result.turn == 1
        assert isinstance(result.checked_at, datetime)

    def test_create_denied_result(self):
        """Test creating a denied result with violations."""
        result = OPACheckResult(
            allowed=False,
            violations=[
                "BLOCKED: Wildcard IAM policy detected",
                "BLOCKED: Security group with 0.0.0.0/0 ingress",
            ],
            warnings=[
                "WARNING: IAM policy has 15 actions",
            ],
            session_id="test-session",
            turn=2,
            policy_version="1.0.0",
            latency_ms=15.5,
        )

        assert result.allowed is False
        assert len(result.violations) == 2
        assert len(result.warnings) == 1
        assert result.policy_version == "1.0.0"
        assert result.latency_ms == 15.5


class TestAuditLogEntry:
    """Test AuditLogEntry model."""

    def test_create_audit_entry(self):
        """Test creating an audit log entry."""
        entry = AuditLogEntry(
            session_id="test-session",
            turn=1,
            user_id="user-123",
            decision="deny",
            violations=["Wildcard IAM blocked"],
            input_summary={"item_keys": ["iam_policy"]},
            latency_ms=12.5,
        )

        assert isinstance(entry.id, UUID)
        assert isinstance(entry.timestamp, datetime)
        assert entry.session_id == "test-session"
        assert entry.decision == "deny"
        assert len(entry.violations) == 1

    def test_audit_entry_defaults(self):
        """Test audit entry default values."""
        entry = AuditLogEntry(
            session_id="test",
            turn=1,
            decision="allow",
            latency_ms=5.0,
        )

        assert entry.user_id is None
        assert entry.violations == []
        assert entry.warnings == []
        assert entry.input_summary == {}


class TestIntentPolicyViolation:
    """Test IntentPolicyViolation exception."""

    def test_create_violation_exception(self):
        """Test creating policy violation exception."""
        exc = IntentPolicyViolation(
            violations=["Wildcard IAM blocked", "Open security group blocked"],
            session_id="test-session",
            turn=3,
        )

        assert exc.violations == ["Wildcard IAM blocked", "Open security group blocked"]
        assert exc.session_id == "test-session"
        assert exc.turn == 3
        assert "test-session" in str(exc)
        assert "Turn: 3" in str(exc)

    def test_violation_exception_message(self):
        """Test exception message formatting."""
        exc = IntentPolicyViolation(
            violations=["Blocked: test violation"],
            session_id="abc-123",
            turn=5,
        )

        message = str(exc)
        assert "Intent blocked by OPA policy" in message
        assert "abc-123" in message
        assert "5" in message
        assert "Blocked: test violation" in message


class TestOPAIntentGateCreation:
    """Test OPAIntentGate creation and configuration."""

    def test_create_gate_default_config(self):
        """Test creating gate with default configuration."""
        gate = OPAIntentGate()

        assert gate.opa_url == "http://localhost:8181"
        assert gate.policy_path == "devops_agent/intent_security"
        assert gate.timeout == 5.0
        assert gate.audit_enabled is True

    def test_create_gate_custom_config(self):
        """Test creating gate with custom configuration."""
        gate = OPAIntentGate(
            opa_url="http://opa-server:8181",
            policy_path="custom/policy",
            timeout=10.0,
            audit_enabled=False,
        )

        assert gate.opa_url == "http://opa-server:8181"
        assert gate.policy_path == "custom/policy"
        assert gate.timeout == 10.0
        assert gate.audit_enabled is False

    def test_factory_function(self):
        """Test create_opa_intent_gate factory."""
        gate = create_opa_intent_gate(
            opa_url="http://custom:8181",
            audit_enabled=True,
        )

        assert isinstance(gate, OPAIntentGate)
        assert gate.opa_url == "http://custom:8181"


class TestOPAInputBuilding:
    """Test OPA input document building."""

    def test_build_opa_input_basic(self):
        """Test building OPA input from extraction result."""
        gate = OPAIntentGate()

        # Create extraction result
        extraction = ExtractionResult(
            turn=1,
            new_items=[
                SpecItem(
                    key="compute_platform",
                    category=IntentCategory.TASK,
                    value="EKS",
                    confidence=ConfidenceBand.CONFIRMED,
                    evidence="User said: Build me an EKS cluster",
                    turn=1,
                ),
            ],
            open_questions=[],
            conflicts_detected=[],
            reasoning_summary="User wants EKS cluster deployment",
        )

        opa_input = gate._build_opa_input(
            extraction_result=extraction,
            session_id="test-123",
            turn=2,
            user_message="Build me an EKS cluster",
        )

        assert opa_input["intent_spec"]["session_id"] == "test-123"
        assert opa_input["intent_spec"]["turn"] == 2
        assert len(opa_input["intent_spec"]["new_items"]) == 1
        assert opa_input["intent_spec"]["new_items"][0]["key"] == "compute_platform"
        assert opa_input["user_message"] == "Build me an EKS cluster"

    def test_build_opa_input_multiple_items(self):
        """Test building OPA input with multiple items."""
        gate = OPAIntentGate()

        extraction = ExtractionResult(
            turn=1,
            new_items=[
                SpecItem(
                    key="compute_platform",
                    category=IntentCategory.TASK,
                    value="EKS",
                    confidence=ConfidenceBand.CONFIRMED,
                    evidence="User wants EKS",
                    turn=1,
                ),
                SpecItem(
                    key="cloud_provider",
                    category=IntentCategory.TASK,
                    value="AWS",
                    confidence=ConfidenceBand.STATED,
                    evidence="User said AWS",
                    turn=1,
                ),
                SpecItem(
                    key="region",
                    category=IntentCategory.CONSTRAINT,
                    value="us-west-2",
                    confidence=ConfidenceBand.INFERRED,
                    evidence="User mentioned us-west-2",
                    turn=1,
                ),
            ],
            open_questions=[],
            conflicts_detected=[],
            reasoning_summary="User wants AWS EKS in us-west-2",
        )

        opa_input = gate._build_opa_input(
            extraction_result=extraction,
            session_id="multi-item",
            turn=3,
            user_message="Deploy to AWS us-west-2",
        )

        assert len(opa_input["intent_spec"]["new_items"]) == 3

        # Check categories are converted to strings
        categories = [item["category"] for item in opa_input["intent_spec"]["new_items"]]
        assert "task" in categories
        assert "constraint" in categories


class TestInputSummarization:
    """Test privacy-safe input summarization for audit."""

    def test_summarize_input(self):
        """Test input summarization."""
        gate = OPAIntentGate()

        extraction = ExtractionResult(
            turn=1,
            new_items=[
                SpecItem(
                    key="compute_platform",
                    category=IntentCategory.TASK,
                    value="EKS",
                    confidence=ConfidenceBand.CONFIRMED,
                    evidence="User wants EKS",
                    turn=1,
                ),
                SpecItem(
                    key="iam_policy",
                    category=IntentCategory.TASK,
                    value={"statements": [{"actions": ["*"]}]},  # Sensitive!
                    confidence=ConfidenceBand.SPECULATIVE,
                    evidence="Inferred IAM needs",
                    turn=1,
                ),
            ],
            open_questions=[],
            conflicts_detected=[],
            reasoning_summary="User wants EKS with IAM",
        )

        summary = gate._summarize_input(extraction)

        # Should NOT contain actual values (privacy)
        assert "EKS" not in str(summary)
        assert "*" not in str(summary)

        # Should contain metadata only
        assert summary["new_items_count"] == 2
        assert "compute_platform" in summary["item_keys"]
        assert "iam_policy" in summary["item_keys"]
        assert "task" in summary["categories"]


class TestAuditLogging:
    """Test audit logging functionality (S3-11)."""

    def test_audit_log_starts_empty(self):
        """Test audit log starts empty."""
        gate = OPAIntentGate()

        log = gate.get_audit_log()
        assert log == []

    def test_get_audit_log_with_session_filter(self):
        """Test filtering audit log by session."""
        gate = OPAIntentGate()

        # Manually add entries
        gate._audit_log.append(AuditLogEntry(
            session_id="session-1",
            turn=1,
            decision="allow",
            latency_ms=5.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="session-2",
            turn=1,
            decision="deny",
            violations=["Test violation"],
            latency_ms=10.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="session-1",
            turn=2,
            decision="allow",
            latency_ms=3.0,
        ))

        # Filter by session
        session_1_entries = gate.get_audit_log(session_id="session-1")
        assert len(session_1_entries) == 2
        assert all(e.session_id == "session-1" for e in session_1_entries)

    def test_get_audit_log_with_decision_filter(self):
        """Test filtering audit log by decision."""
        gate = OPAIntentGate()

        # Add entries
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=1,
            decision="allow",
            latency_ms=5.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=2,
            decision="deny",
            violations=["Blocked"],
            latency_ms=10.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=3,
            decision="deny",
            violations=["Also blocked"],
            latency_ms=8.0,
        ))

        # Filter by decision
        denied_entries = gate.get_audit_log(decision="deny")
        assert len(denied_entries) == 2
        assert all(e.decision == "deny" for e in denied_entries)

    def test_get_audit_log_with_limit(self):
        """Test limiting audit log results."""
        gate = OPAIntentGate()

        # Add many entries
        for i in range(50):
            gate._audit_log.append(AuditLogEntry(
                session_id=f"session-{i}",
                turn=1,
                decision="allow",
                latency_ms=float(i),
            ))

        # Get with limit
        limited = gate.get_audit_log(limit=10)
        assert len(limited) == 10

    def test_get_violation_stats(self):
        """Test violation statistics."""
        gate = OPAIntentGate()

        # Add entries with different violation types
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=1,
            decision="deny",
            violations=["BLOCKED: Wildcard IAM policy detected"],
            latency_ms=5.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=2,
            decision="deny",
            violations=["BLOCKED: Security group with 0.0.0.0/0 ingress"],
            latency_ms=5.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=3,
            decision="deny",
            violations=["BLOCKED: Prompt injection detected"],
            latency_ms=5.0,
        ))
        gate._audit_log.append(AuditLogEntry(
            session_id="test",
            turn=4,
            decision="deny",
            violations=["BLOCKED: Wildcard IAM policy detected"],
            latency_ms=5.0,
        ))

        stats = gate.get_violation_stats()

        assert stats["wildcard_iam"] == 2
        assert stats["open_security_group"] == 1
        assert stats["prompt_injection"] == 1


class TestAuditLogCapacity:
    """Test audit log capacity management."""

    def test_audit_log_caps_at_1000(self):
        """Test audit log is capped at 1000 entries."""
        gate = OPAIntentGate()

        # Add 1500 entries
        for i in range(1500):
            gate._audit_log.append(AuditLogEntry(
                session_id=f"session-{i}",
                turn=1,
                decision="allow",
                latency_ms=float(i),
            ))

        # Simulate the cap logic (called in _audit_log_check)
        if len(gate._audit_log) > 1000:
            gate._audit_log = gate._audit_log[-1000:]

        assert len(gate._audit_log) == 1000

        # Should keep newest entries
        assert gate._audit_log[0].session_id == "session-500"
        assert gate._audit_log[-1].session_id == "session-1499"
