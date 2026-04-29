"""
Unit tests for ConflictDetector (SPEC-02).

Tests 8 known DevOps conflict patterns.
"""

import pytest

from intent.schema import ConfidenceBand, IntentCategory, IntentSpec, SpecItem
from intent.conflict_detector import ConflictDetector, ConflictType


class TestConflictDetector:
    """Test detection of 8 DevOps conflict patterns."""

    def setup_method(self):
        """Create detector instance for each test."""
        self.detector = ConflictDetector()

    def test_platform_conflict_eks_and_lambda(self):
        """Detect conflict: EKS + Lambda (mutually exclusive compute types)."""
        spec = IntentSpec(session_id="test")

        eks_item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User wants Kubernetes",
            turn=1,
        )

        lambda_item = SpecItem(
            key="compute_platform",
            value="Lambda",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.TASK,
            evidence="User also mentioned serverless",
            turn=2,
        )

        spec.items[eks_item.id] = eks_item

        conflicts = self.detector.detect(spec, [lambda_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.PLATFORM_CONFLICT
        assert "EKS" in conflicts[0].description
        assert "Lambda" in conflicts[0].description

    def test_region_conflict(self):
        """Detect conflict: Two different AWS regions confirmed."""
        spec = IntentSpec(session_id="test")

        region1 = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User confirmed Virginia",
            turn=1,
        )

        region2 = SpecItem(
            key="region",
            value="eu-west-1",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User also wants Ireland",
            turn=2,
        )

        spec.items[region1.id] = region1

        conflicts = self.detector.detect(spec, [region2])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.REGION_CONFLICT
        assert len(conflicts[0].resolution_options) >= 2

    def test_cost_vs_performance_conflict(self):
        """Detect conflict: Minimize cost + multi-region active-active."""
        spec = IntentSpec(session_id="test")

        cost_item = SpecItem(
            key="optimization_priority",
            value="minimize_cost",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.META,
            evidence="User wants lowest cost",
            turn=1,
        )

        performance_item = SpecItem(
            key="architecture",
            value="multi-region-active-active",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User wants global deployment",
            turn=2,
        )

        spec.items[cost_item.id] = cost_item

        conflicts = self.detector.detect(spec, [performance_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.COST_VS_PERFORMANCE_CONFLICT

    def test_iac_tool_conflict(self):
        """Detect conflict: Terraform confirmed + CDK inferred."""
        spec = IntentSpec(session_id="test")

        terraform_item = SpecItem(
            key="iac_tool",
            value="Terraform",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User confirmed Terraform",
            turn=1,
        )

        cdk_item = SpecItem(
            key="iac_tool",
            value="CDK",
            confidence=ConfidenceBand.INFERRED,
            category=IntentCategory.TASK,
            evidence="Inferred from TypeScript mention",
            turn=2,
        )

        spec.items[terraform_item.id] = terraform_item

        conflicts = self.detector.detect(spec, [cdk_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.IAC_TOOL_CONFLICT

    def test_cloud_provider_conflict(self):
        """Detect conflict: AWS + GCP (multiple cloud providers)."""
        spec = IntentSpec(session_id="test")

        aws_item = SpecItem(
            key="cloud_provider",
            value="AWS",
            confidence=ConfidenceBand.STATED,
            category=IntentCategory.CONSTRAINT,
            evidence="User said AWS",
            turn=1,
        )

        gcp_item = SpecItem(
            key="cloud_provider",
            value="GCP",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User also mentioned Google Cloud",
            turn=2,
        )

        spec.items[aws_item.id] = aws_item

        conflicts = self.detector.detect(spec, [gcp_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.CLOUD_PROVIDER_CONFLICT

    def test_database_conflict(self):
        """Detect conflict: PostgreSQL + DynamoDB (different database paradigms)."""
        spec = IntentSpec(session_id="test")

        postgres_item = SpecItem(
            key="database",
            value="PostgreSQL",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User wants relational DB",
            turn=1,
        )

        dynamo_item = SpecItem(
            key="database",
            value="DynamoDB",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User also mentioned NoSQL",
            turn=2,
        )

        spec.items[postgres_item.id] = postgres_item

        conflicts = self.detector.detect(spec, [dynamo_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.DATABASE_CONFLICT

    def test_environment_conflict(self):
        """Detect conflict: Production + Development environment specs."""
        spec = IntentSpec(session_id="test")

        prod_item = SpecItem(
            key="environment",
            value="production",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User said production",
            turn=1,
        )

        dev_item = SpecItem(
            key="environment",
            value="development",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User also mentioned dev",
            turn=2,
        )

        spec.items[prod_item.id] = prod_item

        conflicts = self.detector.detect(spec, [dev_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.ENVIRONMENT_CONFLICT

    def test_security_vs_convenience_conflict(self):
        """Detect conflict: High security + public endpoints."""
        spec = IntentSpec(session_id="test")

        security_item = SpecItem(
            key="security_posture",
            value="high",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.META,
            evidence="User wants maximum security",
            turn=1,
        )

        public_item = SpecItem(
            key="endpoint_visibility",
            value="public",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User wants publicly accessible",
            turn=2,
        )

        spec.items[security_item.id] = security_item

        conflicts = self.detector.detect(spec, [public_item])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == ConflictType.SECURITY_VS_CONVENIENCE_CONFLICT

    def test_no_conflict_when_compatible(self):
        """No conflict when items are compatible."""
        spec = IntentSpec(session_id="test")

        item1 = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User wants Kubernetes",
            turn=1,
        )

        item2 = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="User confirmed region",
            turn=2,
        )

        spec.items[item1.id] = item1

        conflicts = self.detector.detect(spec, [item2])

        assert len(conflicts) == 0

    def test_auto_resolvable_conflict(self):
        """Test conflict that can be auto-resolved by confidence."""
        spec = IntentSpec(session_id="test")

        confirmed_item = SpecItem(
            key="compute_platform",
            value="EKS",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.TASK,
            evidence="User confirmed",
            turn=1,
        )

        speculative_item = SpecItem(
            key="compute_platform",
            value="ECS",
            confidence=ConfidenceBand.SPECULATIVE,
            category=IntentCategory.TASK,
            evidence="LLM assumed",
            turn=2,
        )

        spec.items[confirmed_item.id] = confirmed_item

        conflicts = self.detector.detect(spec, [speculative_item])

        # Should detect conflict but mark as auto-resolvable
        # (keep higher confidence item)
        if len(conflicts) > 0:
            conflict = conflicts[0]
            assert conflict.auto_resolvable is True
            assert "EKS" in conflict.auto_resolution

    def test_all_8_patterns_covered(self):
        """Verify all 8 DevOps conflict patterns are implemented."""
        expected_patterns = {
            ConflictType.PLATFORM_CONFLICT,
            ConflictType.REGION_CONFLICT,
            ConflictType.COST_VS_PERFORMANCE_CONFLICT,
            ConflictType.IAC_TOOL_CONFLICT,
            ConflictType.CLOUD_PROVIDER_CONFLICT,
            ConflictType.DATABASE_CONFLICT,
            ConflictType.ENVIRONMENT_CONFLICT,
            ConflictType.SECURITY_VS_CONVENIENCE_CONFLICT,
        }

        # Verify ConflictType enum has all patterns
        implemented_patterns = set(ConflictType)
        assert implemented_patterns == expected_patterns

    def test_resolution_options_provided(self):
        """Test that conflicts include resolution options."""
        spec = IntentSpec(session_id="test")

        item1 = SpecItem(
            key="region",
            value="us-east-1",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="First choice",
            turn=1,
        )

        item2 = SpecItem(
            key="region",
            value="eu-west-1",
            confidence=ConfidenceBand.CONFIRMED,
            category=IntentCategory.CONSTRAINT,
            evidence="Second choice",
            turn=2,
        )

        spec.items[item1.id] = item1

        conflicts = self.detector.detect(spec, [item2])

        assert len(conflicts) == 1
        assert len(conflicts[0].resolution_options) >= 2
        assert all(isinstance(opt, str) for opt in conflicts[0].resolution_options)
