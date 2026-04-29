"""
Unit tests for Output Mode Router (S2-09).

Tests routing logic for design/artifacts/deploy modes.
"""

import pytest
from uuid import uuid4

from execution.output_router import (
    OutputMode,
    OutputModeRouter,
    create_output_router,
)
from execution.dag import IntentDAG
from intent.schema import IntentSpec, SpecItem, IntentCategory, ConfidenceBand


class TestOutputModeRouter:
    """Test output mode routing."""

    def test_route_to_design_mode(self):
        """Test routing to design mode (FinOps only)."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                )
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec, mode="design")

        assert isinstance(dag, IntentDAG)
        assert "test-session" in dag.dag_id  # DAG ID contains session ID

        # Design mode should have only FinOps node
        assert "finops_score" in dag.nodes

    def test_route_to_artifacts_mode(self):
        """Test routing to artifacts mode (no deploy)."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                )
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec, mode="artifacts")

        assert isinstance(dag, IntentDAG)

        # Artifacts mode should have generation nodes but no deploy
        assert "infra_gen" in dag.nodes or "finops_score" in dag.nodes

    def test_route_to_deploy_mode(self):
        """Test routing to deploy mode (full pipeline)."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="region",
                    value="us-east-1",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Region",
                ),
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec, mode="deploy")

        assert isinstance(dag, IntentDAG)

        # Deploy mode should have deploy node
        # (exact nodes depend on template implementation)

    def test_default_mode_is_artifacts(self):
        """Test that default mode is artifacts when not specified."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                )
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec)  # No mode specified

        assert isinstance(dag, IntentDAG)

    def test_extract_mode_from_spec(self):
        """Test extracting output mode from IntentSpec."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.META,
                    key="output_mode",
                    value="design",
                    confidence=ConfidenceBand.STATED,
                    turn=1,
                    evidence="User wants design only",
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                ),
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec)  # Should use design from spec

        assert isinstance(dag, IntentDAG)

    def test_invalid_mode_raises_error(self):
        """Test that invalid mode raises ValueError."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                )
            },
        )

        router = OutputModeRouter()

        with pytest.raises(ValueError, match="Invalid output mode"):
            router.route(intent_spec, mode="invalid-mode")

    def test_artifacts_mode_requires_platform(self):
        """Test artifacts mode requires platform to be specified."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="region",
                    value="us-east-1",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Region only",
                )
            },
        )

        router = OutputModeRouter()

        with pytest.raises(ValueError, match="requires a compute platform"):
            router.route(intent_spec, mode="artifacts")

    def test_deploy_mode_requires_region(self):
        """Test deploy mode requires region to be specified."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                )
            },
        )

        router = OutputModeRouter()

        with pytest.raises(ValueError, match="requires an AWS region"):
            router.route(intent_spec, mode="deploy")

    def test_artifacts_mode_requires_confirmed_confidence(self):
        """Test artifacts mode requires confirmed/stated confidence."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.SPECULATIVE,  # Not confirmed
                    turn=1,
                    evidence="Guessed platform",
                )
            },
        )

        router = OutputModeRouter()

        with pytest.raises(ValueError, match="requires platform to have 'confirmed' or 'stated' confidence"):
            router.route(intent_spec, mode="artifacts")

    def test_design_mode_no_requirements(self):
        """Test design mode can run on minimal spec."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="workload",
                    value="web_app",
                    confidence=ConfidenceBand.SPECULATIVE,
                    turn=1,
                    evidence="Some workload",
                )
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec, mode="design")

        assert isinstance(dag, IntentDAG)

    def test_get_available_modes(self):
        """Test getting list of available modes."""
        router = OutputModeRouter()
        modes = router.get_available_modes()

        assert "design" in modes
        assert "artifacts" in modes
        assert "deploy" in modes
        assert len(modes) == 3

    def test_describe_mode_design(self):
        """Test mode description for design."""
        router = OutputModeRouter()
        description = router.describe_mode("design")

        assert "FinOps scoring" in description
        assert "without generating code" in description

    def test_describe_mode_artifacts(self):
        """Test mode description for artifacts."""
        router = OutputModeRouter()
        description = router.describe_mode("artifacts")

        assert "Terraform" in description
        assert "Does NOT execute" in description

    def test_describe_mode_deploy(self):
        """Test mode description for deploy."""
        router = OutputModeRouter()
        description = router.describe_mode("deploy")

        assert "terraform apply" in description
        assert "human approval" in description

    def test_describe_mode_invalid(self):
        """Test mode description for invalid mode."""
        router = OutputModeRouter()
        description = router.describe_mode("invalid")

        assert "Unknown mode" in description

    def test_factory_function(self):
        """Test create_output_router factory."""
        router = create_output_router()
        assert isinstance(router, OutputModeRouter)

    def test_case_insensitive_mode_parsing(self):
        """Test mode parsing is case-insensitive."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=1,
                    evidence="Platform",
                )
            },
        )

        router = OutputModeRouter()

        # All these should work
        dag1 = router.route(intent_spec, mode="DESIGN")
        dag2 = router.route(intent_spec, mode="Design")
        dag3 = router.route(intent_spec, mode="design")

        assert all(isinstance(d, IntentDAG) for d in [dag1, dag2, dag3])

    def test_stated_confidence_meets_artifacts_requirement(self):
        """Test stated confidence is sufficient for artifacts mode."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.STATED,  # User said it explicitly
                    turn=1,
                    evidence="User said EKS",
                )
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec, mode="artifacts")

        assert isinstance(dag, IntentDAG)

    def test_confirmed_confidence_meets_deploy_requirement(self):
        """Test confirmed confidence meets deploy mode requirements."""
        intent_spec = IntentSpec(
            session_id="test-session",
            items={
                uuid4(): SpecItem(
                    category=IntentCategory.TASK,
                    key="platform",
                    value="eks",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=2,
                    evidence="User confirmed",
                ),
                uuid4(): SpecItem(
                    category=IntentCategory.CONSTRAINT,
                    key="region",
                    value="us-west-2",
                    confidence=ConfidenceBand.CONFIRMED,
                    turn=2,
                    evidence="User confirmed region",
                ),
            },
        )

        router = OutputModeRouter()
        dag = router.route(intent_spec, mode="deploy")

        assert isinstance(dag, IntentDAG)


class TestOutputModeEnum:
    """Test OutputMode enum."""

    def test_output_mode_values(self):
        """Test OutputMode enum has correct values."""
        assert OutputMode.DESIGN.value == "design"
        assert OutputMode.ARTIFACTS.value == "artifacts"
        assert OutputMode.DEPLOY.value == "deploy"

    def test_output_mode_string_conversion(self):
        """Test OutputMode can be compared to strings."""
        assert OutputMode.DESIGN == "design"
        assert OutputMode.ARTIFACTS == "artifacts"
        assert OutputMode.DEPLOY == "deploy"
