"""
DAGExecutor - Async parallel execution engine (SPEC-03).

Executes IntentDAG with wave-based parallelism, dependency resolution,
and graceful error handling.
"""

import asyncio
import time
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from execution.dag import DependencyOutputMissingError, IntentDAG, NodeStatus
from observability.agent_tracer import record_dag_execution


class ExecutionResult(BaseModel):
    """Result of DAG execution."""

    dag_id: str = Field(..., description="DAG identifier")
    session_id: str = Field(..., description="Session identifier")
    success: bool = Field(..., description="True if all nodes completed successfully")
    completed_nodes: list[str] = Field(
        default_factory=list, description="List of successfully completed node IDs"
    )
    failed_nodes: list[str] = Field(
        default_factory=list, description="List of failed node IDs"
    )
    total_nodes: int = Field(..., description="Total number of nodes in DAG")
    execution_time_seconds: float = Field(
        ..., description="Total execution time in seconds"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if execution failed"
    )


class DAGExecutor:
    """
    Executes IntentDAG with async parallel execution.

    Strategy:
    1. Compute topological sort to get execution waves
    2. Execute each wave in parallel using asyncio.gather
    3. Propagate outputs between nodes via resolve_inputs
    4. Stop on first failure (don't execute dependent nodes)
    5. Track execution metrics and status
    """

    def __init__(
        self,
        agent_registry: dict[str, Callable[..., Any]],
    ):
        """
        Initialize DAG executor.

        Args:
            agent_registry: Mapping of task_type → async callable
        """
        self.agent_registry = agent_registry

    async def execute(self, dag: IntentDAG) -> ExecutionResult:
        """
        Execute DAG with parallel wave execution.

        Args:
            dag: IntentDAG to execute

        Returns:
            ExecutionResult with execution metadata
        """
        start_time = time.perf_counter()

        completed_nodes = []
        failed_nodes = []
        has_failure = False

        try:
            # Handle empty DAG
            if not dag.nodes:
                return ExecutionResult(
                    dag_id=dag.dag_id,
                    session_id=dag.session_id,
                    success=True,
                    completed_nodes=[],
                    failed_nodes=[],
                    total_nodes=0,
                    execution_time_seconds=time.perf_counter() - start_time,
                )

            # Compute execution waves
            waves = dag.topological_sort()

            # Execute each wave
            for wave_idx, wave in enumerate(waves):
                # Stop execution if previous wave had failures
                if has_failure:
                    break

                # Execute all nodes in wave in parallel
                tasks = []
                for node_id in wave:
                    tasks.append(self._execute_node(dag, node_id))

                # Wait for all nodes in wave to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for node_id, result in zip(wave, results):
                    if isinstance(result, Exception):
                        # Node failed
                        failed_nodes.append(node_id)
                        has_failure = True
                        error_msg = str(result)
                        dag.mark_node_failed(node_id, error_msg)
                    elif result is False:
                        # Node execution returned failure
                        failed_nodes.append(node_id)
                        has_failure = True
                    else:
                        # Node succeeded
                        completed_nodes.append(node_id)

            execution_time = time.perf_counter() - start_time

            # Record metrics
            record_dag_execution(
                dag_id=dag.dag_id,
                session_id=dag.session_id,
                total_nodes=len(dag.nodes),
                completed_nodes=len(completed_nodes),
                failed_nodes=len(failed_nodes),
                execution_time=execution_time,
            )

            return ExecutionResult(
                dag_id=dag.dag_id,
                session_id=dag.session_id,
                success=not has_failure,
                completed_nodes=completed_nodes,
                failed_nodes=failed_nodes,
                total_nodes=len(dag.nodes),
                execution_time_seconds=execution_time,
                error_message=(
                    f"{len(failed_nodes)} node(s) failed" if has_failure else None
                ),
            )

        except Exception as e:
            execution_time = time.perf_counter() - start_time

            return ExecutionResult(
                dag_id=dag.dag_id,
                session_id=dag.session_id,
                success=False,
                completed_nodes=completed_nodes,
                failed_nodes=failed_nodes,
                total_nodes=len(dag.nodes),
                execution_time_seconds=execution_time,
                error_message=f"DAG execution failed: {str(e)}",
            )

    async def _execute_node(self, dag: IntentDAG, node_id: str) -> bool:
        """
        Execute a single node.

        Args:
            dag: Parent DAG
            node_id: Node to execute

        Returns:
            True if successful, False if failed

        Raises:
            Exception: If node execution fails
        """
        node = dag.nodes[node_id]

        try:
            # Mark node as running
            dag.mark_node_running(node_id)

            # Resolve inputs from upstream nodes
            inputs = dag.resolve_inputs(node_id)

            # Get agent callable from registry
            agent_fn = self.agent_registry.get(node.task_type)
            if not agent_fn:
                raise ValueError(
                    f"Agent task type '{node.task_type}' not found in registry. "
                    f"Available types: {list(self.agent_registry.keys())}"
                )

            # Execute agent
            outputs = await agent_fn(**inputs)

            # Merge inputs into outputs for downstream propagation
            outputs.update(inputs)

            # Mark node as complete with outputs
            dag.mark_node_complete(node_id, outputs)

            return True

        except DependencyOutputMissingError as e:
            # Dependency output missing - this is a DAG structure error
            error_msg = f"Dependency error: {str(e)}"
            dag.mark_node_failed(node_id, error_msg)
            raise ValueError(error_msg)

        except Exception as e:
            # Node execution failed
            error_msg = f"Node execution failed: {str(e)}"
            dag.mark_node_failed(node_id, error_msg)
            raise


async def create_executor(agent_registry: dict[str, Callable]) -> DAGExecutor:
    """Factory function to create DAG executor."""
    return DAGExecutor(agent_registry=agent_registry)
