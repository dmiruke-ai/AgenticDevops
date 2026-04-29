"""
Unit tests for DAG templates.

Tests standard workflow templates and output mode routing.
"""

from datetime import datetime, timezone

import pytest

from execution.dag_templates import (
    DAG_TEMPLATES,
    create_artifacts_only_dag,
    create_debug_workflow_dag,
    create_devops_standard_dag,
    create_finops_only_dag,
)
from intent.schema import IntentSpec


class TestDevOpsStandardDAG:
    """Test standard DevOps workflow DAG."""

    def test_create_standard_dag_without_deploy(self):
        """Test creating standard DAG without deployment node."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_devops_standard_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            include_deploy=False,
        )

        # Should have 5 nodes: _context + 4 workflow nodes
        assert len(dag.nodes) == 5
        assert "_context" in dag.nodes
        assert "finops_score" in dag.nodes
        assert "infra_gen" in dag.nodes
        assert "pipeline_gen" in dag.nodes
        assert "iam_gen" in dag.nodes
        assert "deploy" not in dag.nodes

    def test_create_standard_dag_with_deploy(self):
        """Test creating standard DAG with deployment node."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_devops_standard_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            include_deploy=True,
        )

        # Should have 6 nodes including deploy
        assert len(dag.nodes) == 6
        assert "deploy" in dag.nodes

        # Deploy should depend on iam_gen and pipeline_gen
        deploy_node = dag.nodes["deploy"]
        assert "iam_gen" in deploy_node.depends_on
        assert "pipeline_gen" in deploy_node.depends_on

    def test_dag_dependencies(self):
        """Test that DAG has correct dependency structure."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_devops_standard_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            include_deploy=False,
        )

        # Wave 0: finops_score has no dependencies
        assert dag.nodes["finops_score"].depends_on == []

        # Wave 1: infra_gen and pipeline_gen depend on finops_score
        assert "finops_score" in dag.nodes["infra_gen"].depends_on
        assert "finops_score" in dag.nodes["pipeline_gen"].depends_on

        # Wave 2: iam_gen depends on infra_gen
        assert "infra_gen" in dag.nodes["iam_gen"].depends_on

    def test_topological_sort(self):
        """Test that standard DAG produces correct execution waves."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_devops_standard_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            include_deploy=False,
        )

        waves = dag.topological_sort()

        # Should have 3 waves
        # Wave 0: _context, finops_score (both have no dependencies)
        # Wave 1: infra_gen, pipeline_gen (parallel, depend on finops_score)
        # Wave 2: iam_gen (depends on infra_gen)
        assert len(waves) == 3

        # Context and finops_score run in parallel (both have no dependencies)
        assert set(waves[0]) == {"_context", "finops_score"}

        # Infra and pipeline generation are parallel
        assert set(waves[1]) == {"infra_gen", "pipeline_gen"}

        # IAM generation is last
        assert waves[2] == ["iam_gen"]

    def test_input_mappings(self):
        """Test that nodes have correct input mappings."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_devops_standard_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            include_deploy=False,
        )

        # FinOps score gets intent spec from context
        finops_mappings = dag.nodes["finops_score"].input_mappings
        assert "intent_spec_json" in finops_mappings
        assert finops_mappings["intent_spec_json"] == "_context.intent_spec_json"

        # Infra gen gets FinOps recommendations
        infra_mappings = dag.nodes["infra_gen"].input_mappings
        assert "finops_recommendations" in infra_mappings
        assert infra_mappings["finops_recommendations"] == "finops_score.recommendations"

        # IAM gen gets resource info from infra gen
        iam_mappings = dag.nodes["iam_gen"].input_mappings
        assert "resource_arns" in iam_mappings
        assert iam_mappings["resource_arns"] == "infra_gen.resource_arns"

    def test_context_node_outputs(self):
        """Test that context node contains intent spec."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_devops_standard_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            include_deploy=False,
        )

        context = dag.nodes["_context"]
        assert "intent_spec_json" in context.outputs
        assert "approval_required" in context.outputs


class TestFinOpsOnlyDAG:
    """Test FinOps-only workflow (design mode)."""

    def test_create_finops_only_dag(self):
        """Test creating FinOps-only DAG."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_finops_only_dag(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        # Should have only 2 nodes: _context and finops_score
        assert len(dag.nodes) == 2
        assert "_context" in dag.nodes
        assert "finops_score" in dag.nodes

    def test_finops_only_topological_sort(self):
        """Test that FinOps-only DAG has correct execution order."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_finops_only_dag(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        waves = dag.topological_sort()

        # Should have 1 wave (both nodes have no dependencies)
        assert len(waves) == 1
        assert set(waves[0]) == {"_context", "finops_score"}


class TestArtifactsOnlyDAG:
    """Test artifacts-only workflow (skip FinOps)."""

    def test_create_artifacts_only_dag(self):
        """Test creating artifacts-only DAG."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_artifacts_only_dag(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        # Should have 4 nodes: _context + 3 generators
        assert len(dag.nodes) == 4
        assert "_context" in dag.nodes
        assert "infra_gen" in dag.nodes
        assert "pipeline_gen" in dag.nodes
        assert "iam_gen" in dag.nodes
        assert "finops_score" not in dag.nodes

    def test_artifacts_only_dependencies(self):
        """Test that artifacts DAG has no FinOps dependencies."""
        intent_spec = IntentSpec(session_id="test-session")

        dag = create_artifacts_only_dag(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        # Infra and pipeline should have no dependencies (except context implicitly)
        assert dag.nodes["infra_gen"].depends_on == []
        assert dag.nodes["pipeline_gen"].depends_on == []

        # IAM still depends on infra
        assert "infra_gen" in dag.nodes["iam_gen"].depends_on


class TestDebugWorkflowDAG:
    """Test debug workflow DAG."""

    def test_create_debug_dag(self):
        """Test creating debug workflow DAG."""
        intent_spec = IntentSpec(session_id="test-session")
        error_logs = "Error: Failed to deploy EKS cluster"

        dag = create_debug_workflow_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            error_logs=error_logs,
        )

        # Should have 2 nodes: _context and debug_analyzer
        assert len(dag.nodes) == 2
        assert "_context" in dag.nodes
        assert "debug_analyzer" in dag.nodes

    def test_debug_context_outputs(self):
        """Test that debug context contains error logs."""
        intent_spec = IntentSpec(session_id="test-session")
        error_logs = "Error: Failed to deploy EKS cluster"

        dag = create_debug_workflow_dag(
            session_id="test-session",
            intent_spec=intent_spec,
            error_logs=error_logs,
        )

        context = dag.nodes["_context"]
        assert "error_logs" in context.outputs
        assert context.outputs["error_logs"] == error_logs


class TestDAGTemplateRegistry:
    """Test DAG template registry."""

    def test_template_registry_contains_all_modes(self):
        """Test that registry has all output modes."""
        assert "design" in DAG_TEMPLATES
        assert "artifacts" in DAG_TEMPLATES
        assert "deploy" in DAG_TEMPLATES
        assert "full" in DAG_TEMPLATES
        assert "debug" in DAG_TEMPLATES

    def test_registry_design_mode(self):
        """Test design mode template from registry."""
        intent_spec = IntentSpec(session_id="test-session")

        template_fn = DAG_TEMPLATES["design"]
        dag = template_fn(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        # Should be FinOps-only
        assert "finops_score" in dag.nodes
        assert "infra_gen" not in dag.nodes

    def test_registry_deploy_mode(self):
        """Test deploy mode template from registry."""
        intent_spec = IntentSpec(session_id="test-session")

        template_fn = DAG_TEMPLATES["deploy"]
        dag = template_fn(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        # Should include deployment node
        assert "deploy" in dag.nodes

    def test_registry_artifacts_mode(self):
        """Test artifacts mode template from registry."""
        intent_spec = IntentSpec(session_id="test-session")

        template_fn = DAG_TEMPLATES["artifacts"]
        dag = template_fn(
            session_id="test-session",
            intent_spec=intent_spec,
        )

        # Should have generators but no FinOps
        assert "infra_gen" in dag.nodes
        assert "finops_score" not in dag.nodes
