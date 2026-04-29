"""
Standard DAG Templates for DevOps workflows.

Provides pre-configured DAG structures for common use cases.
"""

from datetime import datetime, timezone
from uuid import uuid4

from execution.dag import IntentDAG, TaskNode
from intent.schema import IntentSpec


def create_devops_standard_dag(
    session_id: str,
    intent_spec: IntentSpec,
    include_deploy: bool = False,
) -> IntentDAG:
    """
    Create standard DevOps workflow DAG.

    Workflow:
    ┌─────────────┐
    │ finops_score│ ← Wave 0: Cost/performance analysis
    └──────┬──────┘
           ↓
    ┌──────────────┬──────────────┐
    │  infra_gen   │ pipeline_gen │ ← Wave 1: Parallel generation
    └──────┬───────┴──────────────┘
           ↓
    ┌──────────────┐
    │   iam_gen    │ ← Wave 2: IAM policies (depends on infra)
    └──────┬───────┘
           ↓
    ┌──────────────┐
    │   deploy     │ ← Wave 3: Optional deployment (requires approval)
    └──────────────┘

    Args:
        session_id: Session identifier
        intent_spec: Confirmed IntentSpec to execute
        include_deploy: If True, includes deployment node (requires approval gate)

    Returns:
        IntentDAG ready for execution
    """
    dag_id = f"devops-{session_id}-{uuid4().hex[:8]}"

    nodes = {}

    # Wave 0: FinOps scoring
    nodes["finops_score"] = TaskNode(
        node_id="finops_score",
        task_type="finops_score",
        depends_on=[],
        input_mappings={
            "intent_spec_json": "_context.intent_spec_json",
        },
    )

    # Wave 1: Parallel artifact generation
    nodes["infra_gen"] = TaskNode(
        node_id="infra_gen",
        task_type="terraform_generator",
        depends_on=["finops_score"],
        input_mappings={
            "intent_spec_json": "_context.intent_spec_json",
            "finops_recommendations": "finops_score.recommendations",
        },
    )

    nodes["pipeline_gen"] = TaskNode(
        node_id="pipeline_gen",
        task_type="pipeline_generator",
        depends_on=["finops_score"],
        input_mappings={
            "intent_spec_json": "_context.intent_spec_json",
            "finops_recommendations": "finops_score.recommendations",
        },
    )

    # Wave 2: IAM policy generation (depends on infra outputs)
    nodes["iam_gen"] = TaskNode(
        node_id="iam_gen",
        task_type="iam_generator",
        depends_on=["infra_gen"],
        input_mappings={
            "resource_arns": "infra_gen.resource_arns",
            "resource_types": "infra_gen.resource_types",
            "intent_spec_json": "_context.intent_spec_json",
        },
    )

    # Wave 3: Optional deployment
    if include_deploy:
        nodes["deploy"] = TaskNode(
            node_id="deploy",
            task_type="deployer",
            depends_on=["iam_gen", "pipeline_gen"],
            input_mappings={
                "terraform_code": "infra_gen.terraform_code",
                "iam_policies": "iam_gen.iam_policies",
                "pipeline_yaml": "pipeline_gen.pipeline_yaml",
                "approval_required": "_context.approval_required",
            },
        )

    # Create DAG
    dag = IntentDAG(
        dag_id=dag_id,
        session_id=session_id,
        nodes=nodes,
        created_at=datetime.now(timezone.utc),
    )

    # Pre-populate context outputs (not actual task outputs, just metadata)
    # These are available to all nodes via _context prefix
    dag.nodes["_context"] = TaskNode(
        node_id="_context",
        task_type="context",
        depends_on=[],
        input_mappings={},
        outputs={
            "intent_spec_json": intent_spec.model_dump_json(),
            "approval_required": True,
        },
    )

    return dag


def create_finops_only_dag(
    session_id: str,
    intent_spec: IntentSpec,
) -> IntentDAG:
    """
    Create DAG for FinOps scoring only (no artifact generation).

    Used for "design mode" where user just wants cost/performance analysis.

    Args:
        session_id: Session identifier
        intent_spec: IntentSpec to analyze

    Returns:
        Single-node DAG with finops_score
    """
    dag_id = f"finops-only-{session_id}-{uuid4().hex[:8]}"

    nodes = {
        "_context": TaskNode(
            node_id="_context",
            task_type="context",
            depends_on=[],
            input_mappings={},
            outputs={
                "intent_spec_json": intent_spec.model_dump_json(),
            },
        ),
        "finops_score": TaskNode(
            node_id="finops_score",
            task_type="finops_score",
            depends_on=[],
            input_mappings={
                "intent_spec_json": "_context.intent_spec_json",
            },
        ),
    }

    return IntentDAG(
        dag_id=dag_id,
        session_id=session_id,
        nodes=nodes,
        created_at=datetime.now(timezone.utc),
    )


def create_artifacts_only_dag(
    session_id: str,
    intent_spec: IntentSpec,
) -> IntentDAG:
    """
    Create DAG for artifact generation only (skip FinOps scoring).

    Used when user has already reviewed FinOps and just wants artifacts.

    Args:
        session_id: Session identifier
        intent_spec: Confirmed IntentSpec

    Returns:
        DAG with infra_gen, pipeline_gen, iam_gen
    """
    dag_id = f"artifacts-only-{session_id}-{uuid4().hex[:8]}"

    nodes = {
        "_context": TaskNode(
            node_id="_context",
            task_type="context",
            depends_on=[],
            input_mappings={},
            outputs={
                "intent_spec_json": intent_spec.model_dump_json(),
            },
        ),
        "infra_gen": TaskNode(
            node_id="infra_gen",
            task_type="terraform_generator",
            depends_on=[],
            input_mappings={
                "intent_spec_json": "_context.intent_spec_json",
            },
        ),
        "pipeline_gen": TaskNode(
            node_id="pipeline_gen",
            task_type="pipeline_generator",
            depends_on=[],
            input_mappings={
                "intent_spec_json": "_context.intent_spec_json",
            },
        ),
        "iam_gen": TaskNode(
            node_id="iam_gen",
            task_type="iam_generator",
            depends_on=["infra_gen"],
            input_mappings={
                "resource_arns": "infra_gen.resource_arns",
                "resource_types": "infra_gen.resource_types",
                "intent_spec_json": "_context.intent_spec_json",
            },
        ),
    }

    return IntentDAG(
        dag_id=dag_id,
        session_id=session_id,
        nodes=nodes,
        created_at=datetime.now(timezone.utc),
    )


def create_debug_workflow_dag(
    session_id: str,
    intent_spec: IntentSpec,
    error_logs: str,
) -> IntentDAG:
    """
    Create DAG for debugging workflow.

    Used when user reports an error and wants root cause analysis.

    Args:
        session_id: Session identifier
        intent_spec: Current IntentSpec
        error_logs: Error logs to analyze

    Returns:
        Single-node DAG with debug_analyzer
    """
    dag_id = f"debug-{session_id}-{uuid4().hex[:8]}"

    nodes = {
        "_context": TaskNode(
            node_id="_context",
            task_type="context",
            depends_on=[],
            input_mappings={},
            outputs={
                "intent_spec_json": intent_spec.model_dump_json(),
                "error_logs": error_logs,
            },
        ),
        "debug_analyzer": TaskNode(
            node_id="debug_analyzer",
            task_type="debugger",
            depends_on=[],
            input_mappings={
                "intent_spec_json": "_context.intent_spec_json",
                "error_logs": "_context.error_logs",
            },
        ),
    }

    return IntentDAG(
        dag_id=dag_id,
        session_id=session_id,
        nodes=nodes,
        created_at=datetime.now(timezone.utc),
    )


# Template registry for output mode router
DAG_TEMPLATES = {
    "design": create_finops_only_dag,
    "artifacts": create_artifacts_only_dag,
    "deploy": lambda session_id, intent_spec: create_devops_standard_dag(
        session_id, intent_spec, include_deploy=True
    ),
    "full": create_devops_standard_dag,
    "debug": create_debug_workflow_dag,
}
