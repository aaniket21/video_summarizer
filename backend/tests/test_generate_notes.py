from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_generate_notes_missing_transcript_returns_400(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response = client.post("/api/generate-notes", json={})
    assert response.status_code == 400
    assert response.json() == {"error": "Missing transcript."}


def test_generate_notes_missing_api_key_returns_500(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = client.post("/api/generate-notes", json={"transcript": "hello"})
    assert response.status_code == 500
    error = response.json().get("error")
    assert isinstance(error, str)
    assert "All providers failed:" in error


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

    def fake_generate_notes(transcript: str, chapters: list, **kwargs):
        assert transcript == "hello world"
        assert chapters == []
        assert kwargs["style"] == "student_notes"
        assert kwargs["output_language"] == "en"
        return {
            "title": "Lecture Title",
            "style": "student_notes",
            "outputLanguage": "en",
            "notesMarkdown": "# Lecture Title\n",
            "tldr": "A concise summary.",
            "keyConcepts": ["Concept 1"],
            "sections": [{"heading": "Overview", "content": "Details.", "keyPoints": ["Point 1"]}],
            "definitions": [{"term": "Term", "definition": "Meaning"}],
            "quizQuestions": [{"question": "What is the key idea?", "options": ["A", "B"], "answerIndex": 0, "explanation": "A is correct."}],
            "flashcards": [{"front": "Term", "back": "Meaning", "tags": ["lecture"]}],
            "speakerLabels": ["Speaker 1"],
            "chatReady": True,
        }

    monkeypatch.setattr(main, "generate_notes_payload", fake_generate_notes, raising=False)

    response = client.post(
        "/api/generate-notes",
        json={
            "transcript": "hello world",
            "chapters": [],
            "style": "student_notes",
            "output_language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Lecture Title"
    assert data["style"] == "student_notes"
    assert data["outputLanguage"] == "en"
    assert data["notesMarkdown"] == "# Lecture Title\n"
    assert isinstance(data["quizQuestions"], list)
    assert isinstance(data["flashcards"], list)


def test_chat_with_job_uses_transcript_context_and_returns_citations(monkeypatch):
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-chat",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {
            "title": "Chat Job",
            "course": "Sample 101",
            "transcript": "Normalization reduces duplication. Redis was mentioned as a cache.",
            "notes_markdown": "# Chat Job\n\nNormalization reduces duplication.",
        },
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    response = client.post(
        f"/api/v1/jobs/{job_id}/chat",
        json={"question": "What did the speaker say about Redis?", "transcript": payload["metadata"]["transcript"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("answer"), str)
    assert isinstance(data.get("citations"), list)
    assert data.get("citations")
