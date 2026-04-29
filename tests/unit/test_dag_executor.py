"""
Unit tests for DAGExecutor (SPEC-03).

Tests async parallel execution, wave-based scheduling, and error handling.
"""

import asyncio
from datetime import datetime

import pytest

from execution.dag import IntentDAG, NodeStatus, TaskNode
from execution.executor import DAGExecutor, ExecutionResult


class MockAgentNode:
    """Mock agent node for testing."""

    def __init__(self, delay: float = 0.01, should_fail: bool = False):
        self.delay = delay
        self.should_fail = should_fail
        self.call_count = 0
        self.call_times = []

    async def execute(self, **kwargs) -> dict:
        """Execute mock task."""
        self.call_count += 1
        self.call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(self.delay)

        if self.should_fail:
            raise ValueError("Mock task failure")

        return {"result": f"output_{self.call_count}", **kwargs}


class TestDAGExecutor:
    """Test DAGExecutor operations."""

    @pytest.mark.asyncio
    async def test_execute_single_node(self):
        """Test executing a single-node DAG."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                )
            },
            created_at=datetime.now(),
        )

        mock_agent = MockAgentNode()
        agent_registry = {"test": mock_agent.execute}

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.success is True
        assert result.completed_nodes == ["A"]
        assert result.failed_nodes == []
        assert mock_agent.call_count == 1
        assert dag.nodes["A"].status == NodeStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_execute_linear_dag(self):
        """Test executing linear DAG: A → B → C."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={"input_a": "A.result"},
                ),
                "C": TaskNode(
                    node_id="C",
                    task_type="test",
                    depends_on=["B"],
                    input_mappings={"input_b": "B.result"},
                ),
            },
            created_at=datetime.now(),
        )

        mock_agent = MockAgentNode()
        agent_registry = {"test": mock_agent.execute}

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.success is True
        assert len(result.completed_nodes) == 3
        assert mock_agent.call_count == 3

        # Check outputs were propagated
        assert "result" in dag.nodes["A"].outputs
        assert "result" in dag.nodes["B"].outputs
        assert "input_a" in dag.nodes["B"].outputs  # Propagated input
        assert "result" in dag.nodes["C"].outputs
        assert "input_b" in dag.nodes["C"].outputs  # Propagated input

    @pytest.mark.asyncio
    async def test_execute_parallel_nodes(self):
        """Test that independent nodes execute in parallel."""
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
            created_at=datetime.now(),
        )

        mock_agent = MockAgentNode(delay=0.1)
        agent_registry = {"test": mock_agent.execute}

        executor = DAGExecutor(agent_registry=agent_registry)

        start = asyncio.get_event_loop().time()
        result = await executor.execute(dag)
        elapsed = asyncio.get_event_loop().time() - start

        assert result.success is True
        assert len(result.completed_nodes) == 3

        # Should complete in ~0.1 seconds (parallel) not ~0.3 (sequential)
        assert elapsed < 0.2, f"Parallel execution took {elapsed}s, expected <0.2s"

        # Check that all nodes started roughly at the same time
        call_times = mock_agent.call_times
        time_spread = max(call_times) - min(call_times)
        assert time_spread < 0.05, "Nodes should start simultaneously"

    @pytest.mark.asyncio
    async def test_execute_diamond_dependency(self):
        """Test diamond dependency: A → B,C → D."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={"from_a": "A.result"},
                ),
                "C": TaskNode(
                    node_id="C",
                    task_type="test",
                    depends_on=["A"],
                    input_mappings={"from_a": "A.result"},
                ),
                "D": TaskNode(
                    node_id="D",
                    task_type="test",
                    depends_on=["B", "C"],
                    input_mappings={"from_b": "B.result", "from_c": "C.result"},
                ),
            },
            created_at=datetime.now(),
        )

        mock_agent = MockAgentNode()
        agent_registry = {"test": mock_agent.execute}

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.success is True
        assert len(result.completed_nodes) == 4
        assert mock_agent.call_count == 4

        # Verify D received inputs from both B and C
        assert "from_b" in dag.nodes["D"].outputs
        assert "from_c" in dag.nodes["D"].outputs

    @pytest.mark.asyncio
    async def test_handle_node_failure(self):
        """Test that node failure is handled gracefully."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                ),
                "B": TaskNode(
                    node_id="B",
                    task_type="fail",
                    depends_on=["A"],
                    input_mappings={},
                ),
                "C": TaskNode(
                    node_id="C",
                    task_type="test",
                    depends_on=["B"],
                    input_mappings={},
                ),
            },
            created_at=datetime.now(),
        )

        mock_success = MockAgentNode()
        mock_failure = MockAgentNode(should_fail=True)
        agent_registry = {"test": mock_success.execute, "fail": mock_failure.execute}

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.success is False
        assert "A" in result.completed_nodes
        assert "B" in result.failed_nodes
        assert "C" not in result.completed_nodes  # C should not execute
        assert dag.nodes["B"].status == NodeStatus.FAILED
        assert dag.nodes["B"].error is not None
        assert dag.nodes["C"].status == NodeStatus.PENDING  # Never executed

    @pytest.mark.asyncio
    async def test_handle_missing_agent(self):
        """Test handling of missing agent in registry."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A",
                    task_type="unknown",
                    depends_on=[],
                    input_mappings={},
                )
            },
            created_at=datetime.now(),
        )

        agent_registry = {}  # Empty registry

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.success is False
        assert "A" in result.failed_nodes
        assert dag.nodes["A"].status == NodeStatus.FAILED
        assert "not found in registry" in dag.nodes["A"].error.lower()

    @pytest.mark.asyncio
    async def test_execution_timing(self):
        """Test that execution result includes timing information."""
        dag = IntentDAG(
            dag_id="test",
            session_id="test",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                )
            },
            created_at=datetime.now(),
        )

        mock_agent = MockAgentNode()
        agent_registry = {"test": mock_agent.execute}

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.execution_time_seconds > 0
        assert result.execution_time_seconds < 1.0  # Should be fast

    @pytest.mark.asyncio
    async def test_empty_dag(self):
        """Test executing an empty DAG."""
        dag = IntentDAG(
            dag_id="test", session_id="test", nodes={}, created_at=datetime.now()
        )

        executor = DAGExecutor(agent_registry={})
        result = await executor.execute(dag)

        assert result.success is True
        assert result.completed_nodes == []
        assert result.failed_nodes == []

    @pytest.mark.asyncio
    async def test_execution_result_metadata(self):
        """Test that ExecutionResult contains proper metadata."""
        dag = IntentDAG(
            dag_id="test-dag-123",
            session_id="session-456",
            nodes={
                "A": TaskNode(
                    node_id="A", task_type="test", depends_on=[], input_mappings={}
                )
            },
            created_at=datetime.now(),
        )

        mock_agent = MockAgentNode()
        agent_registry = {"test": mock_agent.execute}

        executor = DAGExecutor(agent_registry=agent_registry)
        result = await executor.execute(dag)

        assert result.dag_id == "test-dag-123"
        assert result.session_id == "session-456"
        assert result.total_nodes == 1
        assert result.success is True
