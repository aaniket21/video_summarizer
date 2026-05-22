from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_download_audio_missing_url_returns_400():
    response = client.post("/api/download-audio", json={})
    assert response.status_code == 400
    assert response.json() == {"error": "Missing url."}


def test_download_audio_invalid_json_returns_500():
    response = client.post(
        "/api/download-audio",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 500
    error = response.json().get("error")
    assert isinstance(error, str)
    assert error


def test_download_audio_success_returns_payload(monkeypatch):
    from backend.app import main

    def fake_run_download_audio(url: str):
        assert url == "https://example.com/video"
        return {"audioWavBase64": "abc"}

    monkeypatch.setattr(main, "run_download_audio", fake_run_download_audio, raising=False)

    response = client.post(
        "/api/download-audio",
        json={"url": "https://example.com/video"},
    )
    assert response.status_code == 200
    assert response.json() == {"audioWavBase64": "abc"}
