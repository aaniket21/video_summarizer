import os

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_cost_optimization_config(monkeypatch):
    monkeypatch.setenv("COST_OPT_MODEL", "llama-3b")
    monkeypatch.setenv("COST_OPT_PROVIDER", "local")
    monkeypatch.setenv("COST_OPT_ENABLED", "true")

    response = client.get("/api/v1/optimization/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["model"] == "llama-3b"
    assert payload["provider"] == "local"
