from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_generate_notes_missing_transcript_returns_400(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = client.post("/api/generate-notes", json={})
    assert response.status_code == 400
    assert response.json() == {"error": "Missing transcript."}


def test_generate_notes_missing_api_key_returns_500(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = client.post("/api/generate-notes", json={"transcript": ""})
    assert response.status_code == 500
    assert response.json() == {"error": "GEMINI_API_KEY is not configured on the server."}


def test_generate_notes_invalid_json_returns_500(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = client.post(
        "/api/generate-notes",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 500
    error = response.json().get("error")
    assert isinstance(error, str)
    assert error


def test_generate_notes_success_returns_payload(monkeypatch):
    from backend.app import main

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fake_generate_notes(transcript: str, chapters: list):
        assert transcript == "hello world"
        assert chapters == []
        return {"title": "Lecture Title", "notesMarkdown": "# Lecture Title\n"}

    monkeypatch.setattr(main, "generate_notes_payload", fake_generate_notes, raising=False)

    response = client.post(
        "/api/generate-notes",
        json={"transcript": "hello world", "chapters": []},
    )
    assert response.status_code == 200
    assert response.json() == {"title": "Lecture Title", "notesMarkdown": "# Lecture Title\n"}
