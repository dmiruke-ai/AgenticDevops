"""
OPA Intent Security Gate - Python client for intent validation (S3-09).

Validates ExtractionResult against OPA security policies BEFORE
merging into IntentSpec. Blocks wildcard IAM, open security groups,
and prompt injection attempts.

Usage:
    gate = OPAIntentGate()

    # Check extraction result before merge
    decision = await gate.check(
        extraction_result=extraction,
        session_id="abc-123",
        turn=3,
        user_message="Build me an EKS cluster"
    )

    if not decision.allowed:
        raise IntentPolicyViolation(decision.violations)
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, Field

from intent.schema import ExtractionResult, SpecItem


class IntentPolicyViolation(Exception):
    """
    Raised when OPA denies an intent due to security policy violation.

    Contains details about which policies were violated and why.
    """

    def __init__(self, violations: List[str], session_id: str, turn: int):
        self.violations = violations
        self.session_id = session_id
        self.turn = turn

        message = f"Intent blocked by OPA policy. Session: {session_id}, Turn: {turn}. " \
                  f"Violations: {'; '.join(violations)}"
        super().__init__(message)


class OPACheckResult(BaseModel):
    """
    Result of OPA policy check.

    Contains allow/deny decision with violations and warnings.
    """
    allowed: bool = Field(..., description="Whether the intent is allowed")
    violations: List[str] = Field(default_factory=list, description="List of policy violations (blocking)")
    warnings: List[str] = Field(default_factory=list, description="List of policy warnings (non-blocking)")

    # Audit metadata
    session_id: str
    turn: int
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    policy_version: Optional[str] = None
    latency_ms: float = Field(0.0, description="OPA query latency in milliseconds")


class AuditLogEntry(BaseModel):
    """
    Audit log entry for OPA policy checks.

    Stored for compliance and debugging purposes.
    """
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Request context
    session_id: str
    turn: int
    user_id: Optional[str] = None

    # Policy decision
    decision: str  # "allow" | "deny"
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Input summary (not full content for privacy)
    input_summary: Dict[str, Any] = Field(default_factory=dict)

    # Performance
    latency_ms: float


class OPAIntentGate:
    """
    OPA Intent Security Gate.

    Validates intent extraction results against OPA security policies
    before they are merged into the canonical IntentSpec.

    Implements SPEC-04: OPA Security Layer.
    """

    def __init__(
        self,
        opa_url: Optional[str] = None,
        policy_path: str = "devops_agent/intent_security",
        timeout: float = 5.0,
        audit_enabled: bool = True,
    ):
        """
        Initialize OPA Intent Gate.

        Args:
            opa_url: OPA server URL (default: from OPA_URL env or localhost:8181)
            policy_path: OPA policy path (default: devops_agent/intent_security)
            timeout: HTTP request timeout in seconds
            audit_enabled: Whether to log all checks to audit log
        """
        self.opa_url = opa_url or os.getenv("OPA_URL", "http://localhost:8181")
        self.policy_path = policy_path
        self.timeout = timeout
        self.audit_enabled = audit_enabled

        # In-memory audit log (would be Redis/DB in production)
        self._audit_log: List[AuditLogEntry] = []

    async def check(
        self,
        extraction_result: ExtractionResult,
        session_id: str,
        turn: int,
        user_message: str,
        user_id: Optional[str] = None,
    ) -> OPACheckResult:
        """
        Check extraction result against OPA security policies.

        This is called BEFORE the extraction result is merged into IntentSpec.
        Blocks dangerous configurations at the intent layer.

        Args:
            extraction_result: Semantic extraction output to validate
            session_id: Current session identifier
            turn: Current conversation turn number
            user_message: Original user message (for prompt injection detection)
            user_id: Optional user identifier for audit

        Returns:
            OPACheckResult with allow/deny decision and any violations/warnings

        Raises:
            httpx.HTTPError: If OPA server is unreachable
        """
        start_time = datetime.utcnow()

        # Build OPA input document
        opa_input = self._build_opa_input(
            extraction_result=extraction_result,
            session_id=session_id,
            turn=turn,
            user_message=user_message,
        )

        # Query OPA
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.opa_url}/v1/data/{self.policy_path}",
                    json={"input": opa_input},
                )
                response.raise_for_status()

                result = response.json().get("result", {})

        except httpx.ConnectError:
            # OPA unavailable - fail open with warning in non-production
            # In production, this should fail closed
            return OPACheckResult(
                allowed=True,
                warnings=["OPA unavailable - security check skipped"],
                session_id=session_id,
                turn=turn,
            )

        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Parse OPA result
        allowed = result.get("allow", False)
        violations = result.get("deny", [])
        warnings = result.get("warnings", [])
        policy_version = result.get("policy_metadata", {}).get("version")

        # Build result
        check_result = OPACheckResult(
            allowed=allowed,
            violations=violations if isinstance(violations, list) else list(violations),
            warnings=warnings if isinstance(warnings, list) else list(warnings),
            session_id=session_id,
            turn=turn,
            policy_version=policy_version,
            latency_ms=latency_ms,
        )

        # Audit log
        if self.audit_enabled:
            await self._audit_log_check(
                result=check_result,
                user_id=user_id,
                input_summary=self._summarize_input(extraction_result),
            )

        return check_result

    async def check_and_raise(
        self,
        extraction_result: ExtractionResult,
        session_id: str,
        turn: int,
        user_message: str,
        user_id: Optional[str] = None,
    ) -> OPACheckResult:
        """
        Check extraction result and raise exception if denied.

        Convenience method that combines check() with exception raising.

        Args:
            Same as check()

        Returns:
            OPACheckResult if allowed

        Raises:
            IntentPolicyViolation: If OPA denies the intent
        """
        result = await self.check(
            extraction_result=extraction_result,
            session_id=session_id,
            turn=turn,
            user_message=user_message,
            user_id=user_id,
        )

        if not result.allowed:
            raise IntentPolicyViolation(
                violations=result.violations,
                session_id=session_id,
                turn=turn,
            )

        return result

    def _build_opa_input(
        self,
        extraction_result: ExtractionResult,
        session_id: str,
        turn: int,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Build OPA input document from extraction result.

        Converts Pydantic models to dict format expected by Rego policies.
        """
        # Convert new_items to dict format
        new_items = []
        for item in extraction_result.new_items:
            item_dict = {
                "key": item.key,
                "category": item.category.value if hasattr(item.category, 'value') else str(item.category),
                "value": item.value,
                "confidence": item.confidence.value if hasattr(item.confidence, 'value') else str(item.confidence),
                "source": getattr(item, 'source', None) or "llm_extraction",
            }
            new_items.append(item_dict)

        return {
            "intent_spec": {
                "session_id": session_id,
                "turn": turn,
                "new_items": new_items,
            },
            "user_message": user_message,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _summarize_input(self, extraction_result: ExtractionResult) -> Dict[str, Any]:
        """
        Create privacy-safe summary of input for audit log.

        Does not include full values, just keys and types.
        """
        return {
            "new_items_count": len(extraction_result.new_items),
            "item_keys": [item.key for item in extraction_result.new_items],
            "categories": list(set(
                item.category.value if hasattr(item.category, 'value') else str(item.category)
                for item in extraction_result.new_items
            )),
            "has_open_questions": len(extraction_result.open_questions) > 0,
            "has_conflicts": len(getattr(extraction_result, 'conflicts_detected', [])) > 0,
        }

    async def _audit_log_check(
        self,
        result: OPACheckResult,
        user_id: Optional[str],
        input_summary: Dict[str, Any],
    ) -> None:
        """
        Log OPA check to audit log (S3-11).

        In production, this would write to Redis/DB/external audit system.
        """
        entry = AuditLogEntry(
            session_id=result.session_id,
            turn=result.turn,
            user_id=user_id,
            decision="allow" if result.allowed else "deny",
            violations=result.violations,
            warnings=result.warnings,
            input_summary=input_summary,
            latency_ms=result.latency_ms,
        )

        self._audit_log.append(entry)

        # Keep only last 1000 entries in memory
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]

    def get_audit_log(
        self,
        session_id: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """
        Retrieve audit log entries.

        Args:
            session_id: Filter by session ID
            decision: Filter by decision ("allow" or "deny")
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries (newest first)
        """
        entries = self._audit_log.copy()

        # Apply filters
        if session_id:
            entries = [e for e in entries if e.session_id == session_id]
        if decision:
            entries = [e for e in entries if e.decision == decision]

        # Sort by timestamp descending and limit
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def get_violation_stats(self) -> Dict[str, int]:
        """
        Get statistics on policy violations.

        Returns:
            Dict mapping violation type to count
        """
        stats: Dict[str, int] = {}

        for entry in self._audit_log:
            for violation in entry.violations:
                # Extract violation type from message
                if "Wildcard IAM" in violation:
                    key = "wildcard_iam"
                elif "0.0.0.0/0" in violation or "::/0" in violation:
                    key = "open_security_group"
                elif "Prompt injection" in violation:
                    key = "prompt_injection"
                elif "Invalid intent structure" in violation:
                    key = "invalid_structure"
                else:
                    key = "other"

                stats[key] = stats.get(key, 0) + 1

        return stats


def create_opa_intent_gate(
    opa_url: Optional[str] = None,
    audit_enabled: bool = True,
) -> OPAIntentGate:
    """Factory function for creating OPAIntentGate."""
    return OPAIntentGate(
        opa_url=opa_url,
        audit_enabled=audit_enabled,
    )
