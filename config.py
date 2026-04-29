"""
Configuration for the AI DevOps Agent Platform.

All tunables in one place for easy adjustment across environments.
"""

from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """
    Central configuration for the agent platform.
    Can be overridden via environment variables.
    """

    # LLM Models
    primary_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o"
    classifier_model: str = "claude-haiku-4-5-20251001"  # cheap, fast for classification
    max_tokens: int = 4096

    # Intent Engine
    max_question_budget: int = 5  # max clarifying questions per session
    max_retry_count: int = 3  # validation loop retries
    confidence_floor_for_irreversible: str = "confirmed"

    # Output
    default_output_mode: str = "artifacts"  # "design" | "artifacts" | "deploy"

    # Gates
    approval_timeout_seconds: int = 300

    # State Store
    redis_url: str = "redis://localhost:6379"
    intent_spec_ttl_seconds: int = 86400  # 24 hours

    # OPA
    opa_url: str = "http://localhost:8181"

    # Observability
    otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090

    # API Keys (should be set via environment variables)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global config instance
config = AgentConfig()
