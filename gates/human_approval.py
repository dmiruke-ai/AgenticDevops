"""
Human-in-the-Loop Approval Gate (S4-02 / SPEC-05).

Gated execution for irreversible operations like terraform apply.
Computes blast radius, cost delta, and requests human approval.

Usage:
    gate = ApprovalGate()

    request = await gate.request_approval(
        session_id="abc-123",
        terraform_plan=plan_output,
        intent_spec=intent_spec,
    )

    # User approves via API or times out
    decision = await gate.wait_for_decision(request.approval_id, timeout=300)

    if decision.approved:
        # Execute terraform apply
        pass
"""

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum

from pydantic import BaseModel, Field

from config import AgentConfig


class ApprovalStatus(str, Enum):
    """Status of approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ResourceChange(BaseModel):
    """A single resource change from terraform plan."""
    resource_type: str = Field(..., description="Resource type (e.g., aws_eks_cluster)")
    resource_name: str = Field(..., description="Resource name (e.g., main)")
    action: str = Field(..., description="Action: create, update, delete, replace")

    # Impact assessment
    is_destructive: bool = Field(False, description="True if delete/replace")
    estimated_downtime_minutes: int = Field(0, description="Estimated downtime")

    # Cost impact (optional)
    monthly_cost_before: Optional[float] = None
    monthly_cost_after: Optional[float] = None


class BlastRadius(BaseModel):
    """
    Blast radius calculation for terraform changes.

    Quantifies the impact of the proposed changes.
    """
    total_resources: int = Field(0, description="Total resources affected")
    resources_to_create: int = Field(0)
    resources_to_update: int = Field(0)
    resources_to_delete: int = Field(0)
    resources_to_replace: int = Field(0)

    # Risk assessment
    has_destructive_changes: bool = Field(False)
    affected_services: List[str] = Field(default_factory=list)
    estimated_downtime_minutes: int = Field(0)

    # Detailed changes
    changes: List[ResourceChange] = Field(default_factory=list)

    @property
    def risk_level(self) -> str:
        """Calculate risk level based on blast radius."""
        if self.resources_to_delete > 0 or self.resources_to_replace > 0:
            return "HIGH"
        elif self.resources_to_update > 3:
            return "MEDIUM"
        elif self.resources_to_create > 0:
            return "LOW"
        return "NONE"


class CostDelta(BaseModel):
    """
    Cost impact of proposed changes.

    Shows monthly cost change before and after.
    """
    monthly_before: float = Field(0.0, description="Monthly cost before changes")
    monthly_after: float = Field(0.0, description="Monthly cost after changes")
    monthly_delta: float = Field(0.0, description="Monthly cost change")

    # Per-resource breakdown
    cost_by_resource: Dict[str, float] = Field(default_factory=dict)

    @property
    def delta_percentage(self) -> float:
        """Calculate percentage change."""
        if self.monthly_before == 0:
            return 100.0 if self.monthly_after > 0 else 0.0
        return ((self.monthly_after - self.monthly_before) / self.monthly_before) * 100


class ApprovalRequest(BaseModel):
    """
    Approval request for human review.

    Contains all information needed to make an informed decision.
    """
    approval_id: UUID = Field(default_factory=uuid4)
    session_id: str

    # Change summary
    blast_radius: BlastRadius
    cost_delta: CostDelta

    # Terraform details
    terraform_plan_summary: str = Field(..., description="Human-readable plan summary")
    resources_to_destroy: List[str] = Field(default_factory=list)

    # Status tracking
    status: ApprovalStatus = Field(ApprovalStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(seconds=300))

    # Decision (filled when approved/rejected)
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None


class ApprovalDecision(BaseModel):
    """
    Decision on an approval request.
    """
    approval_id: UUID
    approved: bool
    status: ApprovalStatus
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_by: Optional[str] = None
    reason: Optional[str] = None


class ApprovalGate:
    """
    Human-in-the-Loop Approval Gate.

    Implements SPEC-05: Gated execution for terraform apply.
    """

    def __init__(self, default_timeout: int = 300):
        """
        Initialize ApprovalGate.

        Args:
            default_timeout: Default timeout in seconds (default: 300 = 5 minutes)
        """
        # Use provided timeout, fall back to config only if using default
        if default_timeout != 300:
            self.default_timeout = default_timeout
        else:
            config = AgentConfig()
            self.default_timeout = config.approval_timeout_seconds or default_timeout

        # In-memory storage (would be Redis in production)
        self._pending_requests: Dict[UUID, ApprovalRequest] = {}
        self._decisions: Dict[UUID, ApprovalDecision] = {}
        self._approval_events: Dict[UUID, asyncio.Event] = {}

    async def request_approval(
        self,
        session_id: str,
        terraform_plan: str,
        intent_spec: Dict[str, Any],
        cost_estimate: Optional[Dict[str, float]] = None,
    ) -> ApprovalRequest:
        """
        Create an approval request for human review.

        Args:
            session_id: Session identifier
            terraform_plan: Terraform plan output
            intent_spec: Current IntentSpec
            cost_estimate: Optional cost estimates per resource

        Returns:
            ApprovalRequest for tracking
        """
        # Parse terraform plan
        blast_radius = self._calculate_blast_radius(terraform_plan)

        # Calculate cost delta
        cost_delta = self._calculate_cost_delta(
            blast_radius=blast_radius,
            cost_estimate=cost_estimate or {},
        )

        # Generate human-readable summary
        plan_summary = self._generate_plan_summary(
            blast_radius=blast_radius,
            cost_delta=cost_delta,
        )

        # Extract resources to destroy
        resources_to_destroy = [
            f"{c.resource_type}.{c.resource_name}"
            for c in blast_radius.changes
            if c.action in ("delete", "replace")
        ]

        # Create request
        request = ApprovalRequest(
            session_id=session_id,
            blast_radius=blast_radius,
            cost_delta=cost_delta,
            terraform_plan_summary=plan_summary,
            resources_to_destroy=resources_to_destroy,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.default_timeout),
        )

        # Store request
        self._pending_requests[request.approval_id] = request
        self._approval_events[request.approval_id] = asyncio.Event()

        return request

    async def wait_for_decision(
        self,
        approval_id: UUID,
        timeout: Optional[int] = None,
    ) -> ApprovalDecision:
        """
        Wait for human decision on approval request.

        Args:
            approval_id: Approval request ID
            timeout: Timeout in seconds (default: use gate's default)

        Returns:
            ApprovalDecision (approved, rejected, or timeout)
        """
        timeout = timeout or self.default_timeout

        # Check if already decided
        if approval_id in self._decisions:
            return self._decisions[approval_id]

        # Wait for decision event
        event = self._approval_events.get(approval_id)
        if not event:
            return ApprovalDecision(
                approval_id=approval_id,
                approved=False,
                status=ApprovalStatus.CANCELLED,
                reason="Approval request not found",
            )

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)

            # Return stored decision
            if approval_id in self._decisions:
                return self._decisions[approval_id]

        except asyncio.TimeoutError:
            # Timeout - mark as timeout
            decision = ApprovalDecision(
                approval_id=approval_id,
                approved=False,
                status=ApprovalStatus.TIMEOUT,
                reason=f"Approval timeout after {timeout} seconds",
            )

            # Update request status
            if approval_id in self._pending_requests:
                self._pending_requests[approval_id].status = ApprovalStatus.TIMEOUT

            self._decisions[approval_id] = decision
            return decision

    async def approve(
        self,
        approval_id: UUID,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ApprovalDecision:
        """
        Approve a pending request.

        Args:
            approval_id: Approval request ID
            decided_by: User who approved
            reason: Optional approval reason

        Returns:
            ApprovalDecision
        """
        return await self._make_decision(
            approval_id=approval_id,
            approved=True,
            decided_by=decided_by,
            reason=reason,
        )

    async def reject(
        self,
        approval_id: UUID,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ApprovalDecision:
        """
        Reject a pending request.

        Args:
            approval_id: Approval request ID
            decided_by: User who rejected
            reason: Rejection reason

        Returns:
            ApprovalDecision
        """
        return await self._make_decision(
            approval_id=approval_id,
            approved=False,
            decided_by=decided_by,
            reason=reason or "Rejected by user",
        )

    async def _make_decision(
        self,
        approval_id: UUID,
        approved: bool,
        decided_by: Optional[str],
        reason: Optional[str],
    ) -> ApprovalDecision:
        """Internal method to record a decision."""
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED

        decision = ApprovalDecision(
            approval_id=approval_id,
            approved=approved,
            status=status,
            decided_by=decided_by,
            reason=reason,
        )

        # Update request status
        if approval_id in self._pending_requests:
            request = self._pending_requests[approval_id]
            request.status = status
            request.decided_at = decision.decided_at
            request.decided_by = decided_by
            request.decision_reason = reason

        # Store decision
        self._decisions[approval_id] = decision

        # Signal waiters
        if approval_id in self._approval_events:
            self._approval_events[approval_id].set()

        return decision

    def get_pending_requests(self, session_id: Optional[str] = None) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        requests = [
            r for r in self._pending_requests.values()
            if r.status == ApprovalStatus.PENDING
        ]

        if session_id:
            requests = [r for r in requests if r.session_id == session_id]

        return requests

    def get_request(self, approval_id: UUID) -> Optional[ApprovalRequest]:
        """Get a specific approval request."""
        return self._pending_requests.get(approval_id)

    def _calculate_blast_radius(self, terraform_plan: str) -> BlastRadius:
        """
        Parse terraform plan output to calculate blast radius.

        Args:
            terraform_plan: Terraform plan output string

        Returns:
            BlastRadius with change details
        """
        changes: List[ResourceChange] = []

        # Regex patterns for terraform plan output
        # Format: # aws_instance.web will be created
        create_pattern = re.compile(r'#\s+([\w_]+)\.([\w_-]+)\s+will be created')
        update_pattern = re.compile(r'#\s+([\w_]+)\.([\w_-]+)\s+will be updated')
        delete_pattern = re.compile(r'#\s+([\w_]+)\.([\w_-]+)\s+will be destroyed')
        replace_pattern = re.compile(r'#\s+([\w_]+)\.([\w_-]+)\s+must be replaced')

        # Parse creates
        for match in create_pattern.finditer(terraform_plan):
            changes.append(ResourceChange(
                resource_type=match.group(1),
                resource_name=match.group(2),
                action="create",
                is_destructive=False,
            ))

        # Parse updates
        for match in update_pattern.finditer(terraform_plan):
            changes.append(ResourceChange(
                resource_type=match.group(1),
                resource_name=match.group(2),
                action="update",
                is_destructive=False,
            ))

        # Parse deletes
        for match in delete_pattern.finditer(terraform_plan):
            changes.append(ResourceChange(
                resource_type=match.group(1),
                resource_name=match.group(2),
                action="delete",
                is_destructive=True,
                estimated_downtime_minutes=self._estimate_downtime(match.group(1)),
            ))

        # Parse replaces
        for match in replace_pattern.finditer(terraform_plan):
            changes.append(ResourceChange(
                resource_type=match.group(1),
                resource_name=match.group(2),
                action="replace",
                is_destructive=True,
                estimated_downtime_minutes=self._estimate_downtime(match.group(1)),
            ))

        # Calculate totals
        return BlastRadius(
            total_resources=len(changes),
            resources_to_create=sum(1 for c in changes if c.action == "create"),
            resources_to_update=sum(1 for c in changes if c.action == "update"),
            resources_to_delete=sum(1 for c in changes if c.action == "delete"),
            resources_to_replace=sum(1 for c in changes if c.action == "replace"),
            has_destructive_changes=any(c.is_destructive for c in changes),
            affected_services=list(set(c.resource_type for c in changes)),
            estimated_downtime_minutes=sum(c.estimated_downtime_minutes for c in changes),
            changes=changes,
        )

    def _estimate_downtime(self, resource_type: str) -> int:
        """Estimate downtime in minutes for resource type."""
        # High-availability resources that cause downtime when deleted
        high_impact = {
            "aws_eks_cluster": 15,
            "aws_rds_cluster": 10,
            "aws_db_instance": 5,
            "aws_elasticache_cluster": 5,
            "aws_lb": 2,
            "aws_nat_gateway": 2,
        }
        return high_impact.get(resource_type, 0)

    def _calculate_cost_delta(
        self,
        blast_radius: BlastRadius,
        cost_estimate: Dict[str, float],
    ) -> CostDelta:
        """
        Calculate cost impact of changes.

        Args:
            blast_radius: Calculated blast radius
            cost_estimate: Cost estimates per resource type

        Returns:
            CostDelta with cost breakdown
        """
        # Default cost estimates per resource type (monthly USD)
        default_costs = {
            "aws_eks_cluster": 72.0,  # Control plane
            "aws_eks_node_group": 150.0,  # Per node group
            "aws_instance": 50.0,  # t3.medium
            "aws_rds_instance": 100.0,
            "aws_db_instance": 100.0,
            "aws_elasticache_cluster": 50.0,
            "aws_lb": 20.0,
            "aws_nat_gateway": 45.0,
            "aws_eip": 5.0,
            "aws_s3_bucket": 5.0,
            "aws_lambda_function": 10.0,
            "aws_ecs_cluster": 0.0,  # No cost for cluster itself
            "aws_ecs_service": 50.0,
        }

        # Merge with provided estimates
        costs = {**default_costs, **cost_estimate}

        monthly_before = 0.0
        monthly_after = 0.0
        cost_by_resource: Dict[str, float] = {}

        for change in blast_radius.changes:
            resource_cost = costs.get(change.resource_type, 0.0)
            resource_key = f"{change.resource_type}.{change.resource_name}"

            if change.action == "create":
                monthly_after += resource_cost
                cost_by_resource[resource_key] = resource_cost
            elif change.action == "delete":
                monthly_before += resource_cost
                cost_by_resource[resource_key] = -resource_cost
            elif change.action in ("update", "replace"):
                monthly_before += resource_cost
                monthly_after += resource_cost
                # No delta for updates

        return CostDelta(
            monthly_before=monthly_before,
            monthly_after=monthly_after,
            monthly_delta=monthly_after - monthly_before,
            cost_by_resource=cost_by_resource,
        )

    def _generate_plan_summary(
        self,
        blast_radius: BlastRadius,
        cost_delta: CostDelta,
    ) -> str:
        """Generate human-readable plan summary."""
        lines = [
            "=" * 60,
            "TERRAFORM DEPLOYMENT APPROVAL REQUEST",
            "=" * 60,
            "",
            f"Risk Level: {blast_radius.risk_level}",
            f"Total Resources Affected: {blast_radius.total_resources}",
            "",
            "Changes:",
            f"  + Create: {blast_radius.resources_to_create}",
            f"  ~ Update: {blast_radius.resources_to_update}",
            f"  - Delete: {blast_radius.resources_to_delete}",
            f"  -/+ Replace: {blast_radius.resources_to_replace}",
            "",
        ]

        if blast_radius.has_destructive_changes:
            lines.extend([
                "WARNING: Destructive changes detected!",
                f"Estimated Downtime: {blast_radius.estimated_downtime_minutes} minutes",
                "",
            ])

        lines.extend([
            "Cost Impact (Monthly):",
            f"  Before: ${cost_delta.monthly_before:.2f}",
            f"  After:  ${cost_delta.monthly_after:.2f}",
            f"  Delta:  ${cost_delta.monthly_delta:+.2f} ({cost_delta.delta_percentage:+.1f}%)",
            "",
        ])

        if blast_radius.changes:
            lines.append("Detailed Changes:")
            for change in blast_radius.changes:
                action_symbol = {
                    "create": "+",
                    "update": "~",
                    "delete": "-",
                    "replace": "-/+",
                }.get(change.action, "?")

                lines.append(f"  {action_symbol} {change.resource_type}.{change.resource_name}")

        lines.extend([
            "",
            "=" * 60,
        ])

        return "\n".join(lines)


def create_approval_gate(default_timeout: int = 300) -> ApprovalGate:
    """Factory function for creating ApprovalGate."""
    return ApprovalGate(default_timeout=default_timeout)
