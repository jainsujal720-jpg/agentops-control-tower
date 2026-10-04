from fastapi.testclient import TestClient

from agentops_api import database
from agentops_api.main import create_app


def test_liveness_does_not_depend_on_database() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_succeeds_when_database_is_reachable(monkeypatch) -> None:
    monkeypatch.setattr(database, "can_connect", lambda: True)
    client = TestClient(create_app())

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


def test_readiness_fails_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(database, "can_connect", lambda: False)
    client = TestClient(create_app())

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"detail": "database is not ready"}
