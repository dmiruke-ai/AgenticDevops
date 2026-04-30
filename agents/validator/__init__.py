"""Terraform validation and error intelligence."""

__all__ = [
    # Error Intelligence
    "TerraformErrorType",
    "TerraformError",
    "ErrorClassificationResult",
    "TerraformErrorClassifier",
    "create_error_classifier",
    "ERROR_FIX_HINTS",
    "PLANNER_INSTRUCTIONS",
    "build_planner_context",
    # Validation Loop
    "ValidationLoop",
    "ValidationResult",
    "TerraformRunner",
    "create_validation_loop",
]


def __getattr__(name):
    """Lazy import for modules with external dependencies."""
    if name in ("TerraformErrorType", "TerraformError", "ErrorClassificationResult",
                "TerraformErrorClassifier", "create_error_classifier",
                "ERROR_FIX_HINTS", "PLANNER_INSTRUCTIONS", "build_planner_context"):
        from agents.validator.error_intelligence import (
            TerraformErrorType,
            TerraformError,
            ErrorClassificationResult,
            TerraformErrorClassifier,
            create_error_classifier,
            ERROR_FIX_HINTS,
            PLANNER_INSTRUCTIONS,
            build_planner_context,
        )
        mapping = {
            "TerraformErrorType": TerraformErrorType,
            "TerraformError": TerraformError,
            "ErrorClassificationResult": ErrorClassificationResult,
            "TerraformErrorClassifier": TerraformErrorClassifier,
            "create_error_classifier": create_error_classifier,
            "ERROR_FIX_HINTS": ERROR_FIX_HINTS,
            "PLANNER_INSTRUCTIONS": PLANNER_INSTRUCTIONS,
            "build_planner_context": build_planner_context,
        }
        return mapping[name]
    elif name in ("ValidationLoop", "ValidationResult", "TerraformRunner", "create_validation_loop"):
        from agents.validator.validation_loop import (
            ValidationLoop,
            ValidationResult,
            TerraformRunner,
            create_validation_loop,
        )
        mapping = {
            "ValidationLoop": ValidationLoop,
            "ValidationResult": ValidationResult,
            "TerraformRunner": TerraformRunner,
            "create_validation_loop": create_validation_loop,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
