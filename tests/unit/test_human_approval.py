"""
Unit tests for Human Approval Gate (S4-02 / SPEC-05).

Tests blast radius calculation, cost delta, and approval workflow.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import UUID

from gates.human_approval import (
    ApprovalGate,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalStatus,
    BlastRadius,
    CostDelta,
    ResourceChange,
    create_approval_gate,
)


class TestResourceChange:
    """Test ResourceChange model."""

    def test_create_resource_change(self):
        """Test creating a resource change."""
        change = ResourceChange(
            resource_type="aws_eks_cluster",
            resource_name="main",
            action="create",
        )

        assert change.resource_type == "aws_eks_cluster"
        assert change.resource_name == "main"
        assert change.action == "create"
        assert change.is_destructive is False

    def test_destructive_change(self):
        """Test destructive change marking."""
        change = ResourceChange(
            resource_type="aws_db_instance",
            resource_name="production",
            action="delete",
            is_destructive=True,
            estimated_downtime_minutes=10,
        )

        assert change.is_destructive is True
        assert change.estimated_downtime_minutes == 10


class TestBlastRadius:
    """Test BlastRadius model."""

    def test_create_blast_radius(self):
        """Test creating blast radius."""
        blast = BlastRadius(
            total_resources=5,
            resources_to_create=3,
            resources_to_update=1,
            resources_to_delete=1,
        )

        assert blast.total_resources == 5
        assert blast.resources_to_create == 3
        assert blast.has_destructive_changes is False

    def test_risk_level_high(self):
        """Test HIGH risk level with deletes."""
        blast = BlastRadius(
            total_resources=3,
            resources_to_delete=1,
        )

        assert blast.risk_level == "HIGH"

    def test_risk_level_high_with_replace(self):
        """Test HIGH risk level with replaces."""
        blast = BlastRadius(
            total_resources=2,
            resources_to_replace=1,
        )

        assert blast.risk_level == "HIGH"

    def test_risk_level_medium(self):
        """Test MEDIUM risk level with many updates."""
        blast = BlastRadius(
            total_resources=5,
            resources_to_update=4,
        )

        assert blast.risk_level == "MEDIUM"

    def test_risk_level_low(self):
        """Test LOW risk level with creates only."""
        blast = BlastRadius(
            total_resources=3,
            resources_to_create=3,
        )

        assert blast.risk_level == "LOW"

    def test_risk_level_none(self):
        """Test NONE risk level with no changes."""
        blast = BlastRadius()

        assert blast.risk_level == "NONE"


class TestCostDelta:
    """Test CostDelta model."""

    def test_create_cost_delta(self):
        """Test creating cost delta."""
        cost = CostDelta(
            monthly_before=100.0,
            monthly_after=150.0,
            monthly_delta=50.0,
        )

        assert cost.monthly_before == 100.0
        assert cost.monthly_after == 150.0
        assert cost.monthly_delta == 50.0

    def test_delta_percentage_increase(self):
        """Test delta percentage for cost increase."""
        cost = CostDelta(
            monthly_before=100.0,
            monthly_after=150.0,
            monthly_delta=50.0,
        )

        assert cost.delta_percentage == 50.0

    def test_delta_percentage_decrease(self):
        """Test delta percentage for cost decrease."""
        cost = CostDelta(
            monthly_before=200.0,
            monthly_after=100.0,
            monthly_delta=-100.0,
        )

        assert cost.delta_percentage == -50.0

    def test_delta_percentage_from_zero(self):
        """Test delta percentage from zero baseline."""
        cost = CostDelta(
            monthly_before=0.0,
            monthly_after=100.0,
            monthly_delta=100.0,
        )

        assert cost.delta_percentage == 100.0

    def test_delta_percentage_to_zero(self):
        """Test delta percentage to zero."""
        cost = CostDelta(
            monthly_before=100.0,
            monthly_after=0.0,
            monthly_delta=-100.0,
        )

        assert cost.delta_percentage == -100.0


class TestApprovalRequest:
    """Test ApprovalRequest model."""

    def test_create_approval_request(self):
        """Test creating approval request."""
        blast = BlastRadius(
            total_resources=2,
            resources_to_create=2,
        )
        cost = CostDelta(
            monthly_after=100.0,
            monthly_delta=100.0,
        )

        request = ApprovalRequest(
            session_id="test-session",
            blast_radius=blast,
            cost_delta=cost,
            terraform_plan_summary="Plan: +2 to add",
        )

        assert isinstance(request.approval_id, UUID)
        assert request.session_id == "test-session"
        assert request.status == ApprovalStatus.PENDING
        assert request.blast_radius.total_resources == 2

    def test_request_has_expiry(self):
        """Test request has expiration time."""
        blast = BlastRadius()
        cost = CostDelta()

        request = ApprovalRequest(
            session_id="test",
            blast_radius=blast,
            cost_delta=cost,
            terraform_plan_summary="Plan",
        )

        assert request.expires_at > request.created_at


class TestApprovalDecision:
    """Test ApprovalDecision model."""

    def test_create_approved_decision(self):
        """Test creating approved decision."""
        decision = ApprovalDecision(
            approval_id=UUID("12345678-1234-5678-1234-567812345678"),
            approved=True,
            status=ApprovalStatus.APPROVED,
            decided_by="user@example.com",
        )

        assert decision.approved is True
        assert decision.status == ApprovalStatus.APPROVED

    def test_create_rejected_decision(self):
        """Test creating rejected decision."""
        decision = ApprovalDecision(
            approval_id=UUID("12345678-1234-5678-1234-567812345678"),
            approved=False,
            status=ApprovalStatus.REJECTED,
            reason="Security concerns",
        )

        assert decision.approved is False
        assert decision.reason == "Security concerns"


class TestApprovalGateCreation:
    """Test ApprovalGate creation."""

    def test_create_gate_default_timeout(self):
        """Test creating gate with default timeout."""
        gate = ApprovalGate()

        assert gate.default_timeout == 300

    def test_create_gate_custom_timeout(self):
        """Test creating gate with custom timeout."""
        gate = ApprovalGate(default_timeout=600)

        assert gate.default_timeout == 600

    def test_factory_function(self):
        """Test create_approval_gate factory."""
        gate = create_approval_gate(default_timeout=120)

        assert isinstance(gate, ApprovalGate)
        assert gate.default_timeout == 120


class TestBlastRadiusCalculation:
    """Test blast radius calculation from terraform plan."""

    def test_parse_create_resources(self):
        """Test parsing resource creations."""
        gate = ApprovalGate()

        plan = """
        # aws_eks_cluster.main will be created
        # aws_eks_node_group.workers will be created
        # aws_iam_role.eks will be created
        """

        blast = gate._calculate_blast_radius(plan)

        assert blast.resources_to_create == 3
        assert blast.resources_to_delete == 0
        assert blast.has_destructive_changes is False

    def test_parse_delete_resources(self):
        """Test parsing resource deletions."""
        gate = ApprovalGate()

        plan = """
        # aws_eks_cluster.main will be destroyed
        # aws_db_instance.production will be destroyed
        """

        blast = gate._calculate_blast_radius(plan)

        assert blast.resources_to_delete == 2
        assert blast.has_destructive_changes is True

    def test_parse_update_resources(self):
        """Test parsing resource updates."""
        gate = ApprovalGate()

        plan = """
        # aws_security_group.web will be updated in-place
        # aws_instance.app will be updated in-place
        """

        blast = gate._calculate_blast_radius(plan)

        assert blast.resources_to_update == 2
        assert blast.has_destructive_changes is False

    def test_parse_replace_resources(self):
        """Test parsing resource replacements."""
        gate = ApprovalGate()

        plan = """
        # aws_instance.web must be replaced
        """

        blast = gate._calculate_blast_radius(plan)

        assert blast.resources_to_replace == 1
        assert blast.has_destructive_changes is True

    def test_parse_mixed_changes(self):
        """Test parsing mixed changes."""
        gate = ApprovalGate()

        plan = """
        # aws_eks_cluster.main will be created
        # aws_security_group.web will be updated in-place
        # aws_db_instance.old will be destroyed
        # aws_instance.web must be replaced
        """

        blast = gate._calculate_blast_radius(plan)

        assert blast.total_resources == 4
        assert blast.resources_to_create == 1
        assert blast.resources_to_update == 1
        assert blast.resources_to_delete == 1
        assert blast.resources_to_replace == 1

    def test_estimate_downtime(self):
        """Test downtime estimation for destructive changes."""
        gate = ApprovalGate()

        plan = """
        # aws_eks_cluster.main will be destroyed
        # aws_rds_cluster.db will be destroyed
        """

        blast = gate._calculate_blast_radius(plan)

        # EKS: 15 min, RDS: 10 min
        assert blast.estimated_downtime_minutes == 25


class TestCostCalculation:
    """Test cost delta calculation."""

    def test_cost_for_creates(self):
        """Test cost calculation for created resources."""
        gate = ApprovalGate()

        blast = BlastRadius(
            total_resources=2,
            resources_to_create=2,
            changes=[
                ResourceChange(
                    resource_type="aws_eks_cluster",
                    resource_name="main",
                    action="create",
                ),
                ResourceChange(
                    resource_type="aws_instance",
                    resource_name="web",
                    action="create",
                ),
            ],
        )

        cost = gate._calculate_cost_delta(blast, {})

        # EKS: $72, Instance: $50
        assert cost.monthly_after == 122.0
        assert cost.monthly_delta == 122.0

    def test_cost_for_deletes(self):
        """Test cost calculation for deleted resources."""
        gate = ApprovalGate()

        blast = BlastRadius(
            total_resources=1,
            resources_to_delete=1,
            changes=[
                ResourceChange(
                    resource_type="aws_eks_cluster",
                    resource_name="old",
                    action="delete",
                ),
            ],
        )

        cost = gate._calculate_cost_delta(blast, {})

        assert cost.monthly_before == 72.0
        assert cost.monthly_after == 0.0
        assert cost.monthly_delta == -72.0

    def test_cost_with_custom_estimates(self):
        """Test cost with custom estimates."""
        gate = ApprovalGate()

        blast = BlastRadius(
            total_resources=1,
            resources_to_create=1,
            changes=[
                ResourceChange(
                    resource_type="aws_instance",
                    resource_name="large",
                    action="create",
                ),
            ],
        )

        custom_costs = {"aws_instance": 500.0}  # Larger instance
        cost = gate._calculate_cost_delta(blast, custom_costs)

        assert cost.monthly_after == 500.0


class TestPlanSummary:
    """Test plan summary generation."""

    def test_generate_summary_basic(self):
        """Test generating basic summary."""
        gate = ApprovalGate()

        blast = BlastRadius(
            total_resources=3,
            resources_to_create=3,
        )
        cost = CostDelta(
            monthly_before=0.0,
            monthly_after=100.0,
            monthly_delta=100.0,
        )

        summary = gate._generate_plan_summary(blast, cost)

        assert "TERRAFORM DEPLOYMENT APPROVAL REQUEST" in summary
        assert "Risk Level: LOW" in summary
        assert "Create: 3" in summary
        assert "After:  $100.00" in summary

    def test_generate_summary_with_destructive(self):
        """Test summary with destructive changes."""
        gate = ApprovalGate()

        blast = BlastRadius(
            total_resources=1,
            resources_to_delete=1,
            has_destructive_changes=True,
            estimated_downtime_minutes=15,
        )
        cost = CostDelta(
            monthly_before=100.0,
            monthly_after=0.0,
            monthly_delta=-100.0,
        )

        summary = gate._generate_plan_summary(blast, cost)

        assert "WARNING: Destructive changes detected!" in summary
        assert "Estimated Downtime: 15 minutes" in summary


class TestApprovalWorkflow:
    """Test approval workflow."""

    @pytest.mark.asyncio
    async def test_request_approval(self):
        """Test creating approval request."""
        gate = ApprovalGate()

        terraform_plan = """
        # aws_eks_cluster.main will be created
        """

        request = await gate.request_approval(
            session_id="test-session",
            terraform_plan=terraform_plan,
            intent_spec={},
        )

        assert request.session_id == "test-session"
        assert request.status == ApprovalStatus.PENDING
        assert request.blast_radius.resources_to_create == 1

    @pytest.mark.asyncio
    async def test_approve_request(self):
        """Test approving a request."""
        gate = ApprovalGate()

        request = await gate.request_approval(
            session_id="test",
            terraform_plan="# aws_instance.web will be created",
            intent_spec={},
        )

        decision = await gate.approve(
            request.approval_id,
            decided_by="admin@example.com",
            reason="Looks good",
        )

        assert decision.approved is True
        assert decision.status == ApprovalStatus.APPROVED
        assert decision.decided_by == "admin@example.com"

    @pytest.mark.asyncio
    async def test_reject_request(self):
        """Test rejecting a request."""
        gate = ApprovalGate()

        request = await gate.request_approval(
            session_id="test",
            terraform_plan="# aws_db_instance.prod will be destroyed",
            intent_spec={},
        )

        decision = await gate.reject(
            request.approval_id,
            decided_by="security@example.com",
            reason="Cannot delete production database",
        )

        assert decision.approved is False
        assert decision.status == ApprovalStatus.REJECTED
        assert "production database" in decision.reason

    @pytest.mark.asyncio
    async def test_wait_for_approval(self):
        """Test waiting for approval with approval signal."""
        gate = ApprovalGate()

        request = await gate.request_approval(
            session_id="test",
            terraform_plan="# aws_instance.web will be created",
            intent_spec={},
        )

        # Approve in background
        async def approve_later():
            await asyncio.sleep(0.1)
            await gate.approve(request.approval_id)

        asyncio.create_task(approve_later())

        decision = await gate.wait_for_decision(request.approval_id, timeout=5)

        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_wait_for_rejection(self):
        """Test waiting for approval with rejection signal."""
        gate = ApprovalGate()

        request = await gate.request_approval(
            session_id="test",
            terraform_plan="# aws_instance.web will be created",
            intent_spec={},
        )

        # Reject in background
        async def reject_later():
            await asyncio.sleep(0.1)
            await gate.reject(request.approval_id, reason="Not approved")

        asyncio.create_task(reject_later())

        decision = await gate.wait_for_decision(request.approval_id, timeout=5)

        assert decision.approved is False
        assert decision.status == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_timeout_returns_timeout_decision(self):
        """Test timeout returns timeout decision."""
        gate = ApprovalGate()

        request = await gate.request_approval(
            session_id="test",
            terraform_plan="# aws_instance.web will be created",
            intent_spec={},
        )

        # Wait with very short timeout
        decision = await gate.wait_for_decision(request.approval_id, timeout=0.1)

        assert decision.approved is False
        assert decision.status == ApprovalStatus.TIMEOUT
        assert "timeout" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_get_pending_requests(self):
        """Test getting pending requests."""
        gate = ApprovalGate()

        # Create multiple requests
        request1 = await gate.request_approval(
            session_id="session-1",
            terraform_plan="# plan 1",
            intent_spec={},
        )
        request2 = await gate.request_approval(
            session_id="session-2",
            terraform_plan="# plan 2",
            intent_spec={},
        )

        # Approve one
        await gate.approve(request1.approval_id)

        # Get pending
        pending = gate.get_pending_requests()

        assert len(pending) == 1
        assert pending[0].approval_id == request2.approval_id

    @pytest.mark.asyncio
    async def test_get_pending_by_session(self):
        """Test filtering pending by session."""
        gate = ApprovalGate()

        await gate.request_approval(
            session_id="session-1",
            terraform_plan="# plan 1",
            intent_spec={},
        )
        request2 = await gate.request_approval(
            session_id="session-2",
            terraform_plan="# plan 2",
            intent_spec={},
        )

        pending = gate.get_pending_requests(session_id="session-2")

        assert len(pending) == 1
        assert pending[0].approval_id == request2.approval_id

    @pytest.mark.asyncio
    async def test_get_request_by_id(self):
        """Test getting specific request."""
        gate = ApprovalGate()

        request = await gate.request_approval(
            session_id="test",
            terraform_plan="# plan",
            intent_spec={},
        )

        retrieved = gate.get_request(request.approval_id)

        assert retrieved is not None
        assert retrieved.approval_id == request.approval_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_request(self):
        """Test getting nonexistent request returns None."""
        gate = ApprovalGate()

        from uuid import uuid4
        retrieved = gate.get_request(uuid4())

        assert retrieved is None


class TestApprovalGateIntegration:
    """Integration tests for approval gate."""

    @pytest.mark.asyncio
    async def test_full_approval_workflow(self):
        """Test complete approval workflow."""
        gate = ApprovalGate()

        # 1. Request approval
        terraform_plan = """
        # aws_eks_cluster.production will be created
        # aws_eks_node_group.workers will be created
        # aws_iam_role.eks will be created
        """

        request = await gate.request_approval(
            session_id="prod-deployment",
            terraform_plan=terraform_plan,
            intent_spec={"platform": "EKS"},
        )

        # 2. Verify blast radius
        assert request.blast_radius.resources_to_create == 3
        assert request.blast_radius.risk_level == "LOW"

        # 3. Verify cost estimate
        # EKS cluster: $72, Node group: $150, IAM: $0
        assert request.cost_delta.monthly_after > 0

        # 4. Approve
        decision = await gate.approve(
            request.approval_id,
            decided_by="ops-team",
            reason="Approved for production",
        )

        # 5. Verify decision
        assert decision.approved is True
        assert decision.status == ApprovalStatus.APPROVED

        # 6. Verify request updated
        updated_request = gate.get_request(request.approval_id)
        assert updated_request.status == ApprovalStatus.APPROVED
        assert updated_request.decided_by == "ops-team"

    @pytest.mark.asyncio
    async def test_destructive_workflow(self):
        """Test workflow with destructive changes."""
        gate = ApprovalGate()

        terraform_plan = """
        # aws_eks_cluster.production will be destroyed
        # aws_rds_cluster.database will be destroyed
        """

        request = await gate.request_approval(
            session_id="cleanup",
            terraform_plan=terraform_plan,
            intent_spec={},
        )

        # High risk due to deletions
        assert request.blast_radius.risk_level == "HIGH"
        assert request.blast_radius.has_destructive_changes is True

        # Should have downtime estimate
        assert request.blast_radius.estimated_downtime_minutes > 0

        # Check summary warns about destructive
        assert "WARNING" in request.terraform_plan_summary
        assert "Destructive" in request.terraform_plan_summary
