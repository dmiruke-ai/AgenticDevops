"""
Unit tests for IntentDAG (SPEC-03).

Tests topological sort, dependency resolution, and cycle detection.
"""

import pytest
from datetime import datetime

from execution.dag import (
    IntentDAG,
    NodeStatus,
    TaskNode,
    CyclicDependencyError,
    DependencyOutputMissingError,
)


class TestTaskNode:
    """Test TaskNode model."""

    def test_create_task_node(self):
        """Test creating a TaskNode."""
        node = TaskNode(
            node_id="finops_score",
            task_type="finops_score",
            depends_on=[],
            input_mappings={},
        )
        assert node.node_id == "finops_score"
        assert node.status == NodeStatus.PENDING
        assert len(node.depends_on) == 0

    def test_task_node_with_dependencies(self):
        """Test TaskNode with dependencies."""
        node = TaskNode(
            node_id="iam_gen",
            task_type="iam_gen",
            depends_on=["infra_gen"],
            input_mappings={"resource_arns": "infra_gen.resource_arns"},
        )
        assert "infra_gen" in node.depends_on
        assert node.input_mappings["resource_arns"] == "infra_gen.resource_arns"


class TestIntentDAG:
    """Test IntentDAG operations."""

    def test_create_empty_dag(self):
        """Test creating an empty DAG."""
        dag = IntentDAG(
            dag_id="test-dag",
            session_id="test-session",
            nodes={},
            created_at=datetime.utcnow(),
        )
        assert dag.dag_id == "test-dag"
        assert len(dag.nodes) == 0

    def test_add_nodes_to_dag(self):
        """Test adding nodes to DAG."""
        dag = IntentDAG(
            dag_id="test-dag",
            session_id="test-session",
            nodes={},
            created_at=datetime.utcnow(),
        )

        node1 = TaskNode(
            node_id="node1",
            task_type="test",
            depends_on=[],
            input_mappings={},
        )
        node2 = TaskNode(
            node_id="node2",
            task_type="test",
            depends_on=["node1"],
            input_mappings={},
        )

        dag.nodes["node1"] = node1
        dag.nodes["node2"] = node2

        assert len(dag.nodes) == 2
        assert "node2" in dag.nodes


class TestTopologicalSort:
    """Test topological sort algorithm."""

    def test_simple_linear_dag(self):
        """Test topological sort on linear DAG: A → B → C."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B", task_type="test", depends_on=["A"], input_mappings={}
                ),
                "C": TaskNode(
                    node_id="C", task_type="test", depends_on=["B"], input_mappings={}
                ),
            },
            created_at=datetime.utcnow(),
        )

        waves = dag.topological_sort()

        assert len(waves) == 3
        assert waves[0] == ["A"]
        assert waves[1] == ["B"]
        assert waves[2] == ["C"]

    def test_parallel_nodes_same_wave(self):
        """Test that independent nodes are in the same wave."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B", task_type="test", depends_on=[], input_mappings={}
                ),
                "C": TaskNode(
                    node_id="C", task_type="test", depends_on=[], input_mappings={}
                ),
            },
            created_at=datetime.utcnow(),
        )

        waves = dag.topological_sort()

        assert len(waves) == 1
        assert set(waves[0]) == {"A", "B", "C"}

    def test_diamond_dependency(self):
        """Test diamond dependency: A → B,C → D."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B", task_type="test", depends_on=["A"], input_mappings={}
                ),
                "C": TaskNode(
                    node_id="C", task_type="test", depends_on=["A"], input_mappings={}
                ),
                "D": TaskNode(
                    node_id="D",
                    task_type="test",
                    depends_on=["B", "C"],
                    input_mappings={},
                ),
            },
            created_at=datetime.utcnow(),
        )

        waves = dag.topological_sort()

        assert len(waves) == 3
        assert waves[0] == ["A"]
        assert set(waves[1]) == {"B", "C"}  # B and C can run in parallel
        assert waves[2] == ["D"]

    def test_three_level_dependency_chain(self):
        """Test 3-level dependency chain."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "level0": TaskNode(
                    node_id="level0",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                ),
                "level1": TaskNode(
                    node_id="level1",
                    task_type="test",
                    depends_on=["level0"],
                    input_mappings={},
                ),
                "level2": TaskNode(
                    node_id="level2",
                    task_type="test",
                    depends_on=["level1"],
                    input_mappings={},
                ),
            },
            created_at=datetime.utcnow(),
        )

        waves = dag.topological_sort()

        assert len(waves) == 3
        assert waves[0] == ["level0"]
        assert waves[1] == ["level1"]
        assert waves[2] == ["level2"]

    def test_cyclic_dependency_raises_error(self):
        """Test that cyclic dependencies raise CyclicDependencyError."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=["B"], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B", task_type="test", depends_on=["A"], input_mappings={}
                ),
            },
            created_at=datetime.utcnow(),
        )

        with pytest.raises(CyclicDependencyError):
            dag.topological_sort()

    def test_self_dependency_raises_error(self):
        """Test that self-dependency raises CyclicDependencyError."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=["A"], input_mappings={}
                ),
            },
            created_at=datetime.utcnow(),
        )

        with pytest.raises(CyclicDependencyError):
            dag.topological_sort()


class TestGetReadyNodes:
    """Test get_ready_nodes method."""

    def test_get_ready_nodes_initial(self):
        """Test getting ready nodes at start (no dependencies)."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                    status=NodeStatus.PENDING,
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={},
                    status=NodeStatus.PENDING,
                ),
            },
            created_at=datetime.utcnow(),
        )

        ready = dag.get_ready_nodes()
        assert ready == ["A"]

    def test_get_ready_nodes_after_completion(self):
        """Test getting ready nodes after some complete."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                    status=NodeStatus.COMPLETE,
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={},
                    status=NodeStatus.PENDING,
                ),
            },
            created_at=datetime.utcnow(),
        )

        ready = dag.get_ready_nodes()
        assert ready == ["B"]

    def test_no_ready_nodes_when_all_complete(self):
        """Test no ready nodes when all are complete."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                    status=NodeStatus.COMPLETE,
                ),
            },
            created_at=datetime.utcnow(),
        )

        ready = dag.get_ready_nodes()
        assert ready == []


class TestResolveInputs:
    """Test resolve_inputs method."""

    def test_resolve_simple_input(self):
        """Test resolving a simple input mapping."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                    outputs={"result": "value_from_A"},
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={"my_input": "A.result"},
                ),
            },
            created_at=datetime.utcnow(),
        )

        resolved = dag.resolve_inputs("B")
        assert resolved["my_input"] == "value_from_A"

    def test_resolve_multiple_inputs(self):
        """Test resolving multiple input mappings."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                    outputs={"value1": "A1", "value2": "A2"},
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={"input1": "A.value1", "input2": "A.value2"},
                ),
            },
            created_at=datetime.utcnow(),
        )

        resolved = dag.resolve_inputs("B")
        assert resolved["input1"] == "A1"
        assert resolved["input2"] == "A2"

    def test_resolve_missing_output_raises_error(self):
        """Test that missing output raises DependencyOutputMissingError."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                    outputs={},  # No outputs set
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={"my_input": "A.result"},
                ),
            },
            created_at=datetime.utcnow(),
        )

        with pytest.raises(DependencyOutputMissingError):
            dag.resolve_inputs("B")

    def test_resolve_empty_input_mappings(self):
        """Test resolving when no input mappings."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="test",
                    depends_on=[],
                    input_mappings={},
                ),
            },
            created_at=datetime.utcnow(),
        )

        resolved = dag.resolve_inputs("A")
        assert resolved == {}
