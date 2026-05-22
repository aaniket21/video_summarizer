import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from google.generativeai import GenerativeModel
from fastapi import FastAPI, Header, Request, WebSocket, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .db.session import get_db
from .db.repository import SQLAlchemyJobRepository, JobStatus
from .db.models import JobModel

app = FastAPI()
def parse_bearer_token(authorization: str | None) -> str | None:
	if not authorization:
		return None
	parts = authorization.split(" ", 1)
	if len(parts) != 2 or parts[0].lower() != "bearer":
		return ""
	return parts[1].strip()


def base64url_decode(value: str) -> bytes:
	padding = "=" * (-len(value) % 4)
	return base64.urlsafe_b64decode(value + padding)


def verify_jwt_hs256(token: str) -> dict:
	secret = os.getenv("SUPABASE_JWT_SECRET", "")
	if not secret:
		raise ValueError("Invalid or expired token")

	parts = token.split(".")
	if len(parts) != 3:
		raise ValueError("Invalid or expired token")

	try:
		header = json.loads(base64url_decode(parts[0]))
		payload = json.loads(base64url_decode(parts[1]))
		provided_sig = base64url_decode(parts[2])
	except Exception as exc:
		raise ValueError("Invalid or expired token") from exc

	if header.get("alg") != "HS256":
		raise ValueError("Invalid or expired token")

	signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
	expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
	if not hmac.compare_digest(provided_sig, expected_sig):
		raise ValueError("Invalid or expired token")

	exp = payload.get("exp")
	if isinstance(exp, (int, float)) and time.time() > exp:
		raise ValueError("Invalid or expired token")

	return payload


def require_auth(authorization: str | None) -> dict:
	token = parse_bearer_token(authorization)
	if token is None:
		raise PermissionError("Authentication required")
	if not token:
		raise ValueError("Invalid or expired token")
	return verify_jwt_hs256(token)


@app.get("/api/profile")
async def get_profile(authorization: str | None = Header(default=None)):
	try:
		require_auth(authorization)
	except PermissionError as exc:
		return JSONResponse({"error": str(exc)}, status_code=401)
	except ValueError as exc:
		return JSONResponse({"error": str(exc)}, status_code=401)

	return JSONResponse({"status": "ok"})


@app.get("/api/admin")
async def get_admin(authorization: str | None = Header(default=None)):
	try:
		claims = require_auth(authorization)
	except PermissionError as exc:
		return JSONResponse({"error": str(exc)}, status_code=401)
	except ValueError as exc:
		return JSONResponse({"error": str(exc)}, status_code=401)

	role = claims.get("role")
	if role != "admin":
		return JSONResponse({"error": "Insufficient permissions"}, status_code=403)

	return JSONResponse({"status": "ok"})


@app.post("/api/v1/jobs", status_code=201)
async def create_job(
    request: Request, 
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    user_id = claims.get("sub")
    if not user_id:
        return JSONResponse({"error": "Invalid token: missing sub claim"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    video_url = body.get("video_url")
    if not video_url:
        return JSONResponse({"error": "Missing video_url"}, status_code=400)

    repo = SQLAlchemyJobRepository(db)
    job = await repo.create(user_id=user_id, video_url=video_url)
    
    response = {
        "job_id": str(job.id),
        "status": job.status.value,
        "queue_position": 1, # Placeholder
        "created_at": job.created_at.isoformat(),
    }

    return JSONResponse(
        response,
        status_code=201,
        headers={"Location": f"/api/v1/jobs/{job.id}"},
    )


@app.get("/api/v1/jobs/{job_id}")
async def get_job(
    job_id: str, 
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    user_id = claims.get("sub")
    
    repo = SQLAlchemyJobRepository(db)
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        return JSONResponse({"error": "Invalid job ID"}, status_code=400)

    job = await repo.get_by_id(job_uuid)
    if not job or job.user_id != user_id:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    return JSONResponse(job.to_dict())


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    user_id = claims.get("sub")

    repo = SQLAlchemyJobRepository(db)
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        return JSONResponse({"error": "Invalid job ID"}, status_code=400)

    job = await repo.get_by_id(job_uuid)
    if not job or job.user_id != user_id:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    # For now, deletion acts as cancellation
    await repo.update_status(job_uuid, JobStatus.CANCELLED)
    
    return JSONResponse({"job_id": job_id, "status": "cancelled"})


@app.post("/api/v1/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    user_id = claims.get("sub")

    repo = SQLAlchemyJobRepository(db)
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        return JSONResponse({"error": "Invalid job ID"}, status_code=400)

    job = await repo.get_by_id(job_uuid)
    if not job or job.user_id != user_id:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    updated = await repo.update_status(job_uuid, JobStatus.PENDING, progress=0.0)
    
    return JSONResponse({"job_id": job_id, "status": updated.status.value})


@app.get("/api/v1/jobs")
async def list_jobs(
    page: int = 1, 
    limit: int = 20, 
    status: str | None = None, 
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    user_id = claims.get("sub")
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    repo = SQLAlchemyJobRepository(db)
    
    job_status = None
    if status:
        try:
            job_status = JobStatus(status)
        except ValueError:
            pass

    jobs = await repo.list_by_user(user_id, limit=limit, offset=offset, status=job_status)
    
    # Note: For accurate 'total', we'd need another repo method, 
    # but for now we'll return what we have or a placeholder.
    return JSONResponse({
        "items": [j.to_dict() for j in jobs],
        "page": page,
        "limit": limit,
        "total": len(jobs), # Simplified
    })


@app.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str, db: AsyncSession = Depends(get_db)):
    await websocket.accept()
    
    # WebSocket auth is tricky with standard Depends, 
    # usually it's passed via query param or subprotocol.
    # For now, let's just use the DB to check if job exists.
    
    repo = SQLAlchemyJobRepository(db)
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        await websocket.close(code=4000)
        return

    job = await repo.get_by_id(job_uuid)
    if not job:
        await websocket.send_json(
            {
                "type": "job.failed",
                "job_id": job_id,
                "status": "failed",
                "error": {"code": "JOB_NOT_FOUND", "message": "Job not found"},
            }
        )
        await websocket.close()
        return

    # In a real async-first arch, we'd subscribe to Redis/PubSub here.
    # For now, we'll send the current state.
    await websocket.send_json(
        {
            "type": "job.queue",
            "job_id": job_id,
            "queue_position": 1,
        }
    )

    await websocket.send_json(
        {
            "type": "job.progress",
            "job_id": job_id,
            "status": job.status.value,
            "progress": job.progress,
            "message": "Connected",
        }
    )
    # Keep connection open for updates (mocking for now)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass


@app.post("/api/v1/uploads")
async def create_upload():
	upload_id = str(uuid.uuid4())
	return JSONResponse({
		"upload_id": upload_id,
		"upload_url": f"https://example.com/uploads/{upload_id}",
	})


@app.post("/api/v1/jobs/{job_id}/chat")
async def chat_with_job(job_id: str, request: Request):
	try:
		body = await request.json()
	except Exception:
		body = {}

	question = str(body.get("question") or "").strip()
	if not question:
		return JSONResponse({"error": "Missing question"}, status_code=400)

	return JSONResponse({
		"answer": "This is a placeholder answer. Connect RAG pipeline to provide real responses.",
		"citations": [],
	})

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "web" / "server" / "download_audio.py"
DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"


def run_download_audio(url: str) -> dict:
	result = subprocess.run(
		["python", str(SCRIPT_PATH), url],
		check=False,
		capture_output=True,
		text=True,
	)

	stdout = (result.stdout or "").strip()
	stderr = (result.stderr or "").strip()
	if result.returncode != 0:
		message = stderr or stdout or f"Command failed: python {SCRIPT_PATH} {url}"
		raise RuntimeError(message)

	try:
		return json.loads(stdout)
	except json.JSONDecodeError as exc:
		raise RuntimeError(f"Failed to parse python output: {exc.msg}") from exc


def sanitize_text(text: str) -> str:
	return text.replace("\r\n", "\n").strip()


def extract_title_from_markdown(markdown: str) -> str:
	match = re.search(r"^#\s+(.*)$", markdown, re.MULTILINE)
	if match and match.group(1):
		return match.group(1).strip()

	for line in markdown.split("\n"):
		candidate = line.strip()
		if candidate:
			return candidate

	return "AI Video Lecture Notes"


def generate_notes_payload(transcript: str, chapters: list) -> dict:
	api_key = os.getenv("GEMINI_API_KEY", "")
	if not api_key:
		raise RuntimeError("GEMINI_API_KEY is not configured on the server.")

	chapter_text = "\n".join(f"- {c}" for c in chapters) if chapters else "- No strong chapter splits found"
	prompt = f"""
Create polished lecture notes based on the transcript below.

Requirements:
- Output valid, clean markdown only.
- Use long paragraphs and readable bullet lists.
- Avoid decorative markdown clutter such as repeated separators or excessive bold markers.
- Make it study-friendly and visually structured for PDF export.
- Cover all important details, examples, interview angles, and edge cases.
- Explain complex concepts in a simple way, as if teaching a beginner.
- For code snippets, use markdown code blocks with appropriate language tags.
- If the transcript is too short, expand on key concepts with general knowledge.
- If the transcript is very long, prioritize clarity and conciseness while covering all major points.
- Include a variety of examples and interview questions that could be asked on the topic.

Output format (in this exact order):
1) Title as a single H1 at the very top (start with "# ")
2) Heading "Quick Revision"
3) Heading "Key Concepts"
4) Heading "Detailed Explanation"
5) Heading "Examples"
6) Heading "Interview Questions"
7) Heading "Summary"

Potential chapter candidates:
{chapter_text}

Transcript:
{transcript}
""".strip()

	genai.configure(api_key=api_key)
	model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
	model = GenerativeModel(model_name)
	result = model.generate_content(prompt)
	markdown = ""
	if hasattr(result, "response") and hasattr(result.response, "text"):
		markdown = result.response.text()
	elif hasattr(result, "text"):
		markdown = result.text

	markdown = sanitize_text(markdown or "")

	if not markdown:
		raise RuntimeError("Gemini returned empty notes.")

	title = extract_title_from_markdown(markdown)

	return {"title": title, "notesMarkdown": markdown}


@app.post("/api/download-audio")
async def download_audio(request: Request):
	try:
		body = await request.json()
	except Exception as exc:
		message = str(exc) or "Download-audio failed."
		return JSONResponse({"error": message}, status_code=500)

	url = str(body.get("url") or "").strip()
	if not url:
		return JSONResponse({"error": "Missing url."}, status_code=400)

	try:
		result = run_download_audio(url)
	except Exception as exc:
		return JSONResponse({"error": str(exc)}, status_code=500)

	if isinstance(result, dict) and result.get("error"):
		return JSONResponse({"error": str(result.get("error"))}, status_code=500)

	return JSONResponse(result)


@app.post("/api/generate-notes")
async def generate_notes(request: Request):
	try:
		body = await request.json()
	except Exception as exc:
		message = str(exc) or "Failed to generate notes."
		return JSONResponse({"error": message}, status_code=500)

	if not os.getenv("GEMINI_API_KEY", ""):
		return JSONResponse({"error": "GEMINI_API_KEY is not configured on the server."}, status_code=500)

	transcript = str(body.get("transcript") or "").strip()
	if not transcript:
		return JSONResponse({"error": "Missing transcript."}, status_code=400)

	chapters = body.get("chapters") if isinstance(body.get("chapters"), list) else []

	try:
		payload = generate_notes_payload(transcript, chapters)
	except Exception as exc:
		return JSONResponse({"error": str(exc)}, status_code=500)

	return JSONResponse(payload)
