"""
Output Mode Router (S2-09).

Routes execution to the correct DAG template based on output mode.
Implements design/artifacts/deploy workflow selection.
"""

from enum import Enum
from typing import Optional

from execution.dag import IntentDAG
from execution.dag_templates import (
    create_devops_standard_dag,
    create_finops_only_dag,
    create_artifacts_only_dag,
)
from intent.schema import IntentSpec


class OutputMode(str, Enum):
    """
    Output mode determines execution depth.

    - DESIGN: FinOps scoring only, no code generation
    - ARTIFACTS: Generates Terraform/YAML but doesn't deploy
    - DEPLOY: Full pipeline including terraform apply
    """
    DESIGN = "design"
    ARTIFACTS = "artifacts"
    DEPLOY = "deploy"


class OutputModeRouter:
    """
    Routes to the correct DAG based on output mode.

    Ensures appropriate gating and validation for each mode.
    """

    def __init__(self):
        self.mode_templates = {
            OutputMode.DESIGN: create_finops_only_dag,
            OutputMode.ARTIFACTS: create_artifacts_only_dag,
            OutputMode.DEPLOY: lambda session_id, intent_spec: create_devops_standard_dag(
                session_id, intent_spec, include_deploy=True
            ),
        }

    def route(self, intent_spec: IntentSpec, mode: Optional[str] = None) -> IntentDAG:
        """
        Route to appropriate DAG based on output mode.

        Args:
            intent_spec: Confirmed IntentSpec
            mode: Output mode string (design/artifacts/deploy), defaults to artifacts

        Returns:
            IntentDAG configured for the requested mode

        Raises:
            ValueError: If mode is invalid or IntentSpec doesn't meet mode requirements
        """
        # Parse mode
        if mode is None:
            mode = self._extract_mode_from_spec(intent_spec)

        output_mode = self._parse_mode(mode)

        # Validate mode requirements
        self._validate_mode_requirements(intent_spec, output_mode)

        # Get DAG template and create DAG
        template_fn = self.mode_templates[output_mode]
        dag = template_fn(intent_spec.session_id, intent_spec)

        return dag

    def _parse_mode(self, mode: str) -> OutputMode:
        """Parse and validate mode string."""
        try:
            return OutputMode(mode.lower())
        except ValueError:
            raise ValueError(
                f"Invalid output mode: {mode}. "
                f"Must be one of: {', '.join(m.value for m in OutputMode)}"
            )

    def _extract_mode_from_spec(self, spec: IntentSpec) -> str:
        """
        Extract output mode from IntentSpec.

        Looks for 'output_mode' or 'mode' items.
        Defaults to 'artifacts' if not specified.
        """
        for item in spec.items.values():
            if item.key in ["output_mode", "mode"]:
                return str(item.value)
        return "artifacts"  # Default

    def _validate_mode_requirements(self, spec: IntentSpec, mode: OutputMode) -> None:
        """
        Validate that IntentSpec meets requirements for the requested mode.

        Requirements:
        - DESIGN: No specific requirements (can run on any spec)
        - ARTIFACTS: Requires confirmed compute platform
        - DEPLOY: Requires confirmed compute platform + region
        """
        if mode == OutputMode.DESIGN:
            # Design mode can run on any spec
            return

        # Check for platform (required for artifacts and deploy)
        platform_item = self._find_item_by_key(spec, ["platform", "compute_platform", "service"])
        if not platform_item:
            raise ValueError(
                f"Output mode '{mode.value}' requires a compute platform to be specified in IntentSpec"
            )

        # Check confidence level for artifacts/deploy
        from intent.schema import ConfidenceBand
        if platform_item.confidence not in [ConfidenceBand.CONFIRMED, ConfidenceBand.STATED]:
            raise ValueError(
                f"Output mode '{mode.value}' requires platform to have 'confirmed' or 'stated' confidence, "
                f"got '{platform_item.confidence.value}'"
            )

        # Deploy mode requires region
        if mode == OutputMode.DEPLOY:
            region_item = self._find_item_by_key(spec, ["region"])
            if not region_item:
                raise ValueError(
                    "Output mode 'deploy' requires an AWS region to be specified in IntentSpec"
                )

    def _find_item_by_key(self, spec: IntentSpec, keys: list[str]):
        """Find first item matching any of the provided keys."""
        for item in spec.items.values():
            if item.key in keys:
                return item
        return None

    def get_available_modes(self) -> list[str]:
        """Get list of available output modes."""
        return [mode.value for mode in OutputMode]

    def describe_mode(self, mode: str) -> str:
        """Get description of what a mode does."""
        descriptions = {
            OutputMode.DESIGN: (
                "Design mode: Runs FinOps scoring only. "
                "Returns architecture recommendation and cost estimates without generating code."
            ),
            OutputMode.ARTIFACTS: (
                "Artifacts mode: Generates Terraform HCL, IAM policies, and CI/CD pipelines. "
                "Does NOT execute terraform apply or deploy to cloud."
            ),
            OutputMode.DEPLOY: (
                "Deploy mode: Full pipeline including terraform apply. "
                "Requires human approval before executing irreversible changes."
            ),
        }

        try:
            parsed_mode = self._parse_mode(mode)
            return descriptions[parsed_mode]
        except ValueError:
            return f"Unknown mode: {mode}"


def create_output_router() -> OutputModeRouter:
    """Factory function for creating OutputModeRouter."""
    return OutputModeRouter()
