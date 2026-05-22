from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_create_job_returns_201_and_location():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Test Lecture", "course": "Sample 101"},
    }

    response = client.post("/api/v1/jobs", json=payload)

    assert response.status_code == 201
    data = response.json()

    job_id = data.get("job_id")
    assert isinstance(job_id, str)
    UUID(job_id)

    assert data.get("status") == "queued"
    assert isinstance(data.get("queue_position"), int)
    assert data.get("queue_position") >= 1

    created_at = data.get("created_at")
    assert isinstance(created_at, str)
    datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    assert response.headers.get("Location") == f"/api/v1/jobs/{job_id}"


def test_get_job_returns_state_shape():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Test Lecture", "course": "Sample 101"},
    }

    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()

    assert data.get("job_id") == job_id
    assert data.get("status") in {
        "queued",
        "downloading",
        "extracting_audio",
        "transcribing",
        "generating_notes",
        "generating_quiz",
        "exporting",
        "completed",
        "failed",
        "cancelled",
        "resolving_source",
        "syncing",
    }
    assert isinstance(data.get("progress"), int)
    assert isinstance(data.get("current_step"), str)
    assert isinstance(data.get("message"), str)
    assert isinstance(data.get("created_at"), str)
    assert isinstance(data.get("updated_at"), str)
    assert isinstance(data.get("estimated_remaining_seconds"), int)
    assert isinstance(data.get("result"), dict)
    assert "error" in data


def test_list_jobs_returns_paginated_results():
    for idx in range(3):
        payload = {
            "source_type": "youtube",
            "source_url": f"https://example.com/video-{idx}",
            "summary_style": "student_notes",
            "output_language": "en",
            "transcription_backend": "whisper",
            "metadata": {"title": f"Test Lecture {idx}", "course": "Sample 101"},
        }
        client.post("/api/v1/jobs", json=payload)

    response = client.get("/api/v1/jobs", params={"page": 1, "limit": 2})
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data.get("items"), list)
    assert data.get("page") == 1
    assert data.get("limit") == 2
    assert isinstance(data.get("total"), int)
    assert len(data["items"]) <= 2


def test_list_jobs_filters_by_status_and_search():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-filter",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Filtering Basics", "course": "Sample 101"},
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    response = client.get(
        "/api/v1/jobs",
        params={"status": "queued", "search": "Filtering"},
    )
    assert response.status_code == 200
    data = response.json()
    items = data.get("items", [])
    assert any(item.get("job_id") == job_id for item in items)
    assert all(item.get("status") == "queued" for item in items)
    assert all(
        "Filtering" in (item.get("result", {}).get("title", "") or "")
        or "Filtering" in (item.get("result", {}).get("summary", "") or "")
        for item in items
    )


def test_delete_job_marks_cancelled():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-delete",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Delete Me", "course": "Sample 101"},
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    response = client.delete(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data.get("job_id") == job_id
    assert data.get("status") == "cancelled"


def test_retry_job_resets_status():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-retry",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Retry Me", "course": "Sample 101"},
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    client.delete(f"/api/v1/jobs/{job_id}")

    response = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data.get("job_id") == job_id
    assert data.get("status") == "queued"


def test_job_websocket_emits_progress_event():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-ws",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "WS Job", "course": "Sample 101"},
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    with client.websocket_connect(f"/ws/jobs/{job_id}") as websocket:
        first = websocket.receive_json()
        data = websocket.receive_json()

    if first.get("type") == "job.progress":
        data = first

    assert data.get("type") == "job.progress"
    assert data.get("job_id") == job_id
    assert data.get("status")
    assert isinstance(data.get("progress"), int)
    assert isinstance(data.get("current_step"), str)
    assert isinstance(data.get("message"), str)
    assert isinstance(data.get("estimated_remaining_seconds"), int)


def test_job_websocket_emits_queue_event():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-ws-queue",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Queue Job", "course": "Sample 101"},
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    with client.websocket_connect(f"/ws/jobs/{job_id}") as websocket:
        data = websocket.receive_json()

    assert data.get("type") == "job.queue"
    assert data.get("job_id") == job_id
    assert isinstance(data.get("queue_position"), int)


def test_create_upload_returns_signed_url():
    response = client.post("/api/v1/uploads")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("upload_id"), str)
    assert isinstance(data.get("upload_url"), str)


def test_job_chat_returns_answer_and_citations():
    payload = {
        "source_type": "youtube",
        "source_url": "https://example.com/video-chat",
        "summary_style": "student_notes",
        "output_language": "en",
        "transcription_backend": "whisper",
        "metadata": {"title": "Chat Job", "course": "Sample 101"},
    }
    created = client.post("/api/v1/jobs", json=payload)
    job_id = created.json().get("job_id")

    response = client.post(
        f"/api/v1/jobs/{job_id}/chat",
        json={"question": "What did the speaker say about indexing?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("answer"), str)
    assert isinstance(data.get("citations"), list)
