import json


def test_get_secret_from_env(monkeypatch):
    from backend.app import secrets

    monkeypatch.delenv("SECRETS_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")

    assert secrets.get_secret("GEMINI_API_KEY") == "env-key"


def test_get_secret_from_file(monkeypatch, tmp_path):
    from backend.app import secrets

    secrets_path = tmp_path / "secrets.json"
    secrets_path.write_text(json.dumps({"GEMINI_API_KEY": "file-key"}))

    monkeypatch.setenv("SECRETS_PROVIDER", "file")
    monkeypatch.setenv("SECRETS_FILE", str(secrets_path))

    assert secrets.get_secret("GEMINI_API_KEY") == "file-key"
