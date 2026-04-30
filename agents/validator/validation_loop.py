"""
Validation Loop - Terraform validation with error intelligence (S3-07).

Implements the error → classify → replan loop:
1. Run terraform validate/plan
2. On error, classify using TerraformErrorClassifier
3. If retryable, invoke SmartReplanner
4. Loop up to MAX_RETRIES times
5. Return final result or escalate to user

Usage:
    validator = ValidationLoop()
    result = await validator.validate_and_fix(
        terraform_files={"main.tf": "...", "iam.tf": "..."},
        intent_spec=intent_spec,
    )
"""

import asyncio
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field

from agents.validator.error_intelligence import (
    TerraformErrorClassifier,
    TerraformErrorType,
    ErrorClassificationResult,
    build_planner_context,
    create_error_classifier,
)
from agents.planner.smart_replanner import (
    SmartReplanner,
    ReplanningInput,
    ReplanningOutput,
    create_smart_replanner,
)
from config import AgentConfig


class ValidationResult(BaseModel):
    """Result of validation loop execution."""
    success: bool
    status: str  # "passed" | "fixed" | "failed" | "escalated"

    # Final artifacts
    terraform_files: Dict[str, str] = Field(default_factory=dict)

    # Validation details
    total_retries: int = 0
    errors_encountered: List[ErrorClassificationResult] = Field(default_factory=list)
    fixes_applied: List[str] = Field(default_factory=list)

    # If escalated
    escalation_reason: Optional[str] = None
    requires_user_input: bool = False

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0


class TerraformRunner:
    """
    Runs Terraform commands for validation.

    Executes terraform init, validate, and plan.
    """

    def __init__(self, working_dir: Optional[Path] = None):
        """
        Initialize TerraformRunner.

        Args:
            working_dir: Working directory for terraform commands.
                         If None, creates a temp directory.
        """
        self.working_dir = working_dir
        self._temp_dir = None

    async def setup(self, terraform_files: Dict[str, str]) -> Path:
        """
        Set up working directory with terraform files.

        Args:
            terraform_files: Dict mapping filename to content

        Returns:
            Path to working directory
        """
        if self.working_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="tf_validate_")
            self.working_dir = Path(self._temp_dir)

        # Write terraform files
        for filename, content in terraform_files.items():
            file_path = self.working_dir / filename
            file_path.write_text(content)

        return self.working_dir

    async def init(self) -> tuple[bool, str]:
        """
        Run terraform init.

        Returns:
            (success, output)
        """
        return await self._run_command(["terraform", "init", "-backend=false"])

    async def validate(self) -> tuple[bool, str]:
        """
        Run terraform validate.

        Returns:
            (success, output)
        """
        return await self._run_command(["terraform", "validate", "-json"])

    async def plan(self) -> tuple[bool, str]:
        """
        Run terraform plan.

        Returns:
            (success, output/error)
        """
        return await self._run_command([
            "terraform", "plan",
            "-out=/dev/null",  # Don't save plan
            "-no-color",
        ])

    async def _run_command(self, cmd: List[str]) -> tuple[bool, str]:
        """
        Run terraform command.

        Args:
            cmd: Command and arguments

        Returns:
            (success, output)
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    cwd=str(self.working_dir),
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    env={**os.environ, "TF_IN_AUTOMATION": "1"},
                )
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr or result.stdout

        except subprocess.TimeoutExpired:
            return False, "Terraform command timed out after 5 minutes"
        except FileNotFoundError:
            return False, "Terraform CLI not found. Please install terraform."

    def cleanup(self):
        """Clean up temporary directory if created."""
        if self._temp_dir:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)


class ValidationLoop:
    """
    Validation loop with error intelligence and smart replanning.

    Implements the core validation → classify → replan loop.
    """

    def __init__(
        self,
        max_retries: int = 3,
        skip_terraform: bool = False,
    ):
        """
        Initialize ValidationLoop.

        Args:
            max_retries: Maximum retry attempts (default: 3)
            skip_terraform: Skip actual terraform commands (for testing)
        """
        config = AgentConfig()
        self.max_retries = max_retries
        self.skip_terraform = skip_terraform

        # Initialize components
        self.classifier = create_error_classifier()
        self.replanner = create_smart_replanner()

    async def validate_and_fix(
        self,
        terraform_files: Dict[str, str],
        intent_spec: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Run validation loop with automatic error fixing.

        Args:
            terraform_files: Dict mapping filename to terraform content
            intent_spec: Current IntentSpec as dict
            session_id: Optional session ID for logging

        Returns:
            ValidationResult with final status and artifacts
        """
        started_at = datetime.utcnow()
        result = ValidationResult(
            success=False,
            status="pending",
            terraform_files=terraform_files.copy(),
            started_at=started_at,
        )

        # Skip actual terraform if flag set (for testing)
        if self.skip_terraform:
            result.success = True
            result.status = "passed"
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
            return result

        # Set up terraform runner
        runner = TerraformRunner()

        try:
            # Initial setup
            await runner.setup(result.terraform_files)

            # Run terraform init
            init_success, init_output = await runner.init()
            if not init_success:
                result.status = "failed"
                result.escalation_reason = f"Terraform init failed: {init_output}"
                result.completed_at = datetime.utcnow()
                result.duration_seconds = (result.completed_at - started_at).total_seconds()
                return result

            # Validation loop
            retry_count = 0

            while retry_count < self.max_retries:
                # Run validation
                validate_success, validate_output = await runner.validate()

                if validate_success:
                    # Validation passed!
                    result.success = True
                    result.status = "fixed" if retry_count > 0 else "passed"
                    break

                # Validation failed - classify error
                retry_count += 1
                result.total_retries = retry_count

                # Extract affected resources from error output
                affected_resources = self._extract_affected_resources(validate_output)

                # Classify error
                classification = self.classifier.classify(
                    stderr_output=validate_output,
                    affected_resources=affected_resources,
                )
                result.errors_encountered.append(classification)

                # Check if error requires user input
                if classification.requires_user_input:
                    result.status = "escalated"
                    result.escalation_reason = classification.error.fix_hint
                    result.requires_user_input = True
                    break

                # Check if we've hit retry limit
                if retry_count >= self.max_retries:
                    result.status = "failed"
                    result.escalation_reason = f"Max retries ({self.max_retries}) exceeded"
                    break

                # Attempt smart replanning
                try:
                    replan_result = await self._attempt_replan(
                        classification=classification,
                        terraform_files=result.terraform_files,
                        intent_spec=intent_spec,
                        retry_count=retry_count,
                    )

                    # Update terraform files with fixes
                    for module_name, fixed_content in replan_result.fixed_modules.items():
                        # Map module name to filename
                        filename = f"{module_name}.tf" if not module_name.endswith(".tf") else module_name
                        result.terraform_files[filename] = fixed_content

                    result.fixes_applied.append(replan_result.fix_summary)

                    # Re-setup with fixed files
                    await runner.setup(result.terraform_files)

                except Exception as e:
                    result.status = "failed"
                    result.escalation_reason = f"Replanning failed: {str(e)}"
                    break

            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()
            return result

        finally:
            runner.cleanup()

    async def _attempt_replan(
        self,
        classification: ErrorClassificationResult,
        terraform_files: Dict[str, str],
        intent_spec: Dict[str, Any],
        retry_count: int,
    ) -> ReplanningOutput:
        """
        Attempt smart replanning for classified error.

        Args:
            classification: Error classification result
            terraform_files: Current terraform files
            intent_spec: Current IntentSpec
            retry_count: Current retry count

        Returns:
            ReplanningOutput with fixed modules
        """
        # Determine passing vs failing modules
        failing_modules = classification.failed_modules or ["main"]

        # Extract module names from file names
        all_modules = [
            name.replace(".tf", "")
            for name in terraform_files.keys()
            if name.endswith(".tf")
        ]

        passing_modules = [
            m for m in all_modules
            if m not in failing_modules and f"{m}.tf" not in failing_modules
        ]

        # Build previous artifacts (only failing ones)
        previous_artifacts = {
            name: content
            for name, content in terraform_files.items()
            if name.replace(".tf", "") in failing_modules or name in failing_modules
        }

        # Create replanning input
        replan_input = ReplanningInput(
            intent_spec=intent_spec,
            passing_modules=passing_modules,
            failing_modules=failing_modules,
            error_classification=classification,
            previous_artifacts=previous_artifacts,
            retry_count=retry_count,
        )

        # Run replanner
        return self.replanner.replan(replan_input)

    def _extract_affected_resources(self, error_output: str) -> List[str]:
        """
        Extract affected resource names from terraform error output.

        Args:
            error_output: Terraform stderr output

        Returns:
            List of resource identifiers (e.g., ["aws_eks_cluster.main"])
        """
        import re

        resources = []

        # Pattern: aws_xxx.name or module.name.aws_xxx.name
        resource_pattern = re.compile(
            r'((?:module\.[a-z_]+\.)?aws_[a-z_]+\.[a-z_0-9]+)',
            re.IGNORECASE
        )

        matches = resource_pattern.findall(error_output)
        resources.extend(matches)

        # Also try: resource "aws_xxx" "name"
        resource_def_pattern = re.compile(
            r'resource\s+"(aws_[a-z_]+)"\s+"([a-z_0-9]+)"',
            re.IGNORECASE
        )

        for type_name, resource_name in resource_def_pattern.findall(error_output):
            resources.append(f"{type_name}.{resource_name}")

        return list(set(resources))


def create_validation_loop(
    max_retries: int = 3,
    skip_terraform: bool = False,
) -> ValidationLoop:
    """Factory function for creating ValidationLoop."""
    return ValidationLoop(
        max_retries=max_retries,
        skip_terraform=skip_terraform,
    )
