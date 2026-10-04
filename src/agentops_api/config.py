"""Environment-based configuration for the API service."""

import os


def database_url() -> str:
    """Return the PostgreSQL URL supplied by the runtime environment."""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://agentops:local_dev_only_change_before_deploy@localhost:5432/agentops",
    )


def gateway_settings() -> dict[str, str]:
    """Return RelayGuard connection and routing identity settings."""
    return {
        "base_url": os.environ.get("RELAYGUARD_BASE_URL", "http://host.docker.internal:8100").rstrip("/"),
        "api_key": os.environ.get("RELAYGUARD_API_KEY", "").strip(),
        "tenant_id": os.environ.get("AGENTOPS_TENANT_ID", "acme").strip(),
        "user_id": os.environ.get("AGENTOPS_USER_ID", "agentops-demo").strip(),
        "task_class": os.environ.get("AGENTOPS_TASK_CLASS", "complex").strip(),
        "timeout_seconds": os.environ.get("RELAYGUARD_TIMEOUT_SECONDS", "60").strip(),
    }
