"""Intent engine for AI DevOps Agent Platform."""

from intent.schema import (
    IntentSpec,
    SpecItem,
    ConfidenceBand,
    IntentCategory,
    ExtractionResult,
    OpenQuestion,
    Conflict,
    TransitionEvent,
)

from intent.confidence import (
    IntentTransitionEngine,
    VALID_TRANSITIONS,
    IRREVERSIBLE_ACTIONS,
)

from intent.conflict_detector import (
    ConflictDetector,
    ConflictType,
)

# Lazy imports for modules with external dependencies (redis)
# These are imported on-demand to allow basic schema usage without redis
def __getattr__(name):
    """Lazy import for modules with external dependencies."""
    if name in ("SessionStateStore", "create_state_store"):
        from intent.state_store import SessionStateStore, create_state_store
        return {"SessionStateStore": SessionStateStore, "create_state_store": create_state_store}[name]
    elif name in ("SessionManager", "SessionInfo", "SessionStatus",
                  "SessionAccessDenied", "SessionNotFound", "SessionExpired",
                  "create_session_manager"):
        from intent.session_manager import (
            SessionManager, SessionInfo, SessionStatus,
            SessionAccessDenied, SessionNotFound, SessionExpired,
            create_session_manager
        )
        mapping = {
            "SessionManager": SessionManager,
            "SessionInfo": SessionInfo,
            "SessionStatus": SessionStatus,
            "SessionAccessDenied": SessionAccessDenied,
            "SessionNotFound": SessionNotFound,
            "SessionExpired": SessionExpired,
            "create_session_manager": create_session_manager,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Schema
    "IntentSpec",
    "SpecItem",
    "ConfidenceBand",
    "IntentCategory",
    "ExtractionResult",
    "OpenQuestion",
    "Conflict",
    "TransitionEvent",
    # Confidence
    "IntentTransitionEngine",
    "VALID_TRANSITIONS",
    "IRREVERSIBLE_ACTIONS",
    # Conflict Detection
    "ConflictDetector",
    "ConflictType",
    # State Store
    "SessionStateStore",
    "create_state_store",
    # Session Manager
    "SessionManager",
    "SessionInfo",
    "SessionStatus",
    "SessionAccessDenied",
    "SessionNotFound",
    "SessionExpired",
    "create_session_manager",
]
