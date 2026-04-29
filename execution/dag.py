"""
IntentDAG - Directed Acyclic Graph execution engine (SPEC-03).

Implements topological sort with Kahn's algorithm for parallel wave execution.
Handles dependency resolution, cycle detection, and cross-node output propagation.
"""

from collections import defaultdict, deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NodeStatus(str, Enum):
    """Task node execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class TaskNode(BaseModel):
    """
    Task node in execution DAG.

    Represents a single agent task with dependencies and I/O mappings.
    """

    node_id: str = Field(..., description="Unique node identifier")
    task_type: str = Field(..., description="Agent task type")
    depends_on: list[str] = Field(
        default_factory=list, description="List of upstream node IDs"
    )
    input_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Input parameter → upstream_node.output_key mappings",
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Task outputs after execution"
    )
    status: NodeStatus = Field(
        default=NodeStatus.PENDING, description="Current execution status"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


class IntentDAG(BaseModel):
    """
    Directed Acyclic Graph for intent execution.

    Orchestrates multi-agent task execution with dependency resolution.
    """

    dag_id: str = Field(..., description="Unique DAG identifier")
    session_id: str = Field(..., description="Associated session ID")
    nodes: dict[str, TaskNode] = Field(
        default_factory=dict, description="Node ID → TaskNode mapping"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="DAG creation timestamp",
    )

    def topological_sort(self) -> list[list[str]]:
        """
        Compute topological sort using Kahn's algorithm.

        Returns execution waves where nodes in the same wave can run in parallel.

        Returns:
            List of waves, where each wave is a list of node IDs that can execute in parallel

        Raises:
            CyclicDependencyError: If the graph contains cycles
        """
        # Build in-degree map and adjacency list
        in_degree = {node_id: 0 for node_id in self.nodes}
        adjacency = defaultdict(list)

        for node_id, node in self.nodes.items():
            for dep in node.depends_on:
                adjacency[dep].append(node_id)
                in_degree[node_id] += 1

        # Initialize queue with nodes that have no dependencies
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

        waves = []
        processed_count = 0

        while queue:
            # Process all nodes in current wave (same depth level)
            wave_size = len(queue)
            current_wave = []

            for _ in range(wave_size):
                node_id = queue.popleft()
                current_wave.append(node_id)
                processed_count += 1

                # Reduce in-degree for downstream nodes
                for neighbor in adjacency[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

            waves.append(current_wave)

        # Check for cycles
        if processed_count != len(self.nodes):
            raise CyclicDependencyError(
                f"Cycle detected in DAG {self.dag_id}. "
                f"Processed {processed_count} of {len(self.nodes)} nodes."
            )

        return waves

    def get_ready_nodes(self) -> list[str]:
        """
        Get list of nodes ready to execute.

        A node is ready if:
        1. Its status is PENDING
        2. All dependencies are COMPLETE

        Returns:
            List of node IDs ready for execution
        """
        ready = []

        for node_id, node in self.nodes.items():
            # Skip if not pending
            if node.status != NodeStatus.PENDING:
                continue

            # Check if all dependencies are complete
            all_deps_complete = all(
                self.nodes[dep_id].status == NodeStatus.COMPLETE
                for dep_id in node.depends_on
                if dep_id in self.nodes
            )

            if all_deps_complete:
                ready.append(node_id)

        return ready

    def resolve_inputs(self, node_id: str) -> dict[str, Any]:
        """
        Resolve input parameters for a node from upstream outputs.

        Parses input_mappings like {"param": "upstream_node.output_key"}
        and retrieves the actual values from upstream node outputs.

        Args:
            node_id: Node ID to resolve inputs for

        Returns:
            Resolved input dictionary

        Raises:
            DependencyOutputMissingError: If referenced output doesn't exist
        """
        node = self.nodes[node_id]
        resolved = {}

        for param_name, mapping in node.input_mappings.items():
            # Parse mapping: "upstream_node.output_key"
            if "." not in mapping:
                raise DependencyOutputMissingError(
                    f"Invalid input mapping format: {mapping}. "
                    f"Expected 'node_id.output_key'"
                )

            upstream_node_id, output_key = mapping.split(".", 1)

            # Check if upstream node exists
            if upstream_node_id not in self.nodes:
                raise DependencyOutputMissingError(
                    f"Upstream node '{upstream_node_id}' not found in DAG"
                )

            upstream_node = self.nodes[upstream_node_id]

            # Check if output exists
            if output_key not in upstream_node.outputs:
                raise DependencyOutputMissingError(
                    f"Output '{output_key}' not found in node '{upstream_node_id}'. "
                    f"Available outputs: {list(upstream_node.outputs.keys())}"
                )

            resolved[param_name] = upstream_node.outputs[output_key]

        return resolved

    def mark_node_running(self, node_id: str) -> None:
        """Mark node as running."""
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.RUNNING

    def mark_node_complete(self, node_id: str, outputs: dict[str, Any]) -> None:
        """Mark node as complete with outputs."""
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.COMPLETE
            self.nodes[node_id].outputs = outputs

    def mark_node_failed(self, node_id: str, error: str) -> None:
        """Mark node as failed with error message."""
        if node_id in self.nodes:
            self.nodes[node_id].status = NodeStatus.FAILED
            self.nodes[node_id].error = error

    def is_complete(self) -> bool:
        """Check if all nodes are complete."""
        return all(node.status == NodeStatus.COMPLETE for node in self.nodes.values())

    def has_failures(self) -> bool:
        """Check if any nodes have failed."""
        return any(node.status == NodeStatus.FAILED for node in self.nodes.values())


class CyclicDependencyError(Exception):
    """Raised when a cycle is detected in the DAG."""

    pass


class DependencyOutputMissingError(Exception):
    """Raised when a required dependency output is missing."""

    pass
