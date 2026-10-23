from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app import create_app


def test_health_returns_ok_without_a_database() -> None:
    """Liveness only: no container (hence no engine) is wired, and /health still answers."""
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
