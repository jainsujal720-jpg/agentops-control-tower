"""Small database connectivity check used by the readiness endpoint."""

import psycopg

from agentops_api.config import database_url


def can_connect() -> bool:
    """Return whether PostgreSQL responds to a simple query."""
    try:
        with psycopg.connect(database_url(), connect_timeout=2) as connection:
            connection.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
