import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import stripe
except ModuleNotFoundError:  # Optional dependency for tests and minimal installs.
    stripe = None
from fastapi import FastAPI, Header, Request, WebSocket, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .db.session import get_db
from .db.repository import SQLAlchemyJobRepository, JobStatus
from .db.billing_repository import BillingRepository
from .db.models import JobModel
from .llm import providers as llm_providers

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


def require_stripe_client():
    if stripe is None:
        raise RuntimeError("stripe is not installed on the server.")
    secret = os.getenv("STRIPE_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured on the server.")
    stripe.api_key = secret
    return stripe


def get_price_id_for_plan(plan: str) -> str:
    if plan == "student":
        return os.getenv("STRIPE_STUDENT_PRICE_ID", "")
    if plan == "pro":
        return os.getenv("STRIPE_PRO_PRICE_ID", "")
    return ""


def map_price_id_to_plan(price_id: str) -> Optional[str]:
    student_price = os.getenv("STRIPE_STUDENT_PRICE_ID", "")
    pro_price = os.getenv("STRIPE_PRO_PRICE_ID", "")
    if student_price and price_id == student_price:
        return "student"
    if pro_price and price_id == pro_price:
        return "pro"
    return None


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
    total_count = await repo.count_by_user(user_id, status=job_status)
    return JSONResponse({
        "items": [j.to_dict() for j in jobs],
        "page": page,
        "limit": limit,
        "total": total_count,
    })


@app.post("/api/v1/billing/checkout")
async def create_billing_checkout(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
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

    plan = str(body.get("plan") or "").strip().lower()
    if plan not in {"student", "pro"}:
        return JSONResponse({"error": "Unsupported plan"}, status_code=400)

    price_id = get_price_id_for_plan(plan)
    if not price_id:
        return JSONResponse({"error": "Stripe price is not configured"}, status_code=500)

    success_url = os.getenv("STRIPE_SUCCESS_URL", "")
    cancel_url = os.getenv("STRIPE_CANCEL_URL", "")
    if not success_url or not cancel_url:
        return JSONResponse({"error": "Stripe redirect URLs are not configured"}, status_code=500)

    try:
        stripe_client = require_stripe_client()
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    billing_repo = BillingRepository(db)
    customer = await billing_repo.get_by_user(user_id)
    if not customer:
        stripe_customer = stripe_client.Customer.create(metadata={"user_id": user_id})
        customer = await billing_repo.upsert_customer(user_id, stripe_customer.id)

    session = stripe_client.checkout.Session.create(
        mode="subscription",
        customer=customer.stripe_customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=True,
    )

    await billing_repo.update_subscription_by_user(
        user_id=user_id,
        plan=plan,
        status="pending",
    )

    return JSONResponse({"url": session.url})


@app.post("/api/v1/billing/portal")
async def create_billing_portal(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    user_id = claims.get("sub")
    if not user_id:
        return JSONResponse({"error": "Invalid token: missing sub claim"}, status_code=401)

    return_url = os.getenv("STRIPE_PORTAL_RETURN_URL", "")
    if not return_url:
        return JSONResponse({"error": "Stripe portal return URL is not configured"}, status_code=500)

    try:
        stripe_client = require_stripe_client()
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    billing_repo = BillingRepository(db)
    customer = await billing_repo.get_by_user(user_id)
    if not customer:
        stripe_customer = stripe_client.Customer.create(metadata={"user_id": user_id})
        customer = await billing_repo.upsert_customer(user_id, stripe_customer.id)

    session = stripe_client.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=return_url,
    )

    return JSONResponse({"url": session.url})


@app.post("/api/v1/billing/webhook")
async def billing_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return JSONResponse({"error": "Stripe webhook secret is not configured"}, status_code=500)

    if stripe is None:
        return JSONResponse({"error": "stripe is not installed on the server."}, status_code=500)

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception:
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    billing_repo = BillingRepository(db)

    if event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        customer_id = str(data.get("customer") or "")
        subscription_id = str(data.get("id") or "")
        status = str(data.get("status") or "") or None
        price_id = None
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = str(items[0].get("price", {}).get("id") or "")

        plan = map_price_id_to_plan(price_id or "")
        period_end = None
        if data.get("current_period_end"):
            period_end = datetime.fromtimestamp(int(data["current_period_end"]), tz=timezone.utc)

        if customer_id:
            await billing_repo.update_subscription_by_customer(
                stripe_customer_id=customer_id,
                plan=plan,
                status=status,
                stripe_subscription_id=subscription_id or None,
                current_period_end=period_end,
            )

    if event_type == "customer.subscription.deleted":
        customer_id = str(data.get("customer") or "")
        if customer_id:
            await billing_repo.update_subscription_by_customer(
                stripe_customer_id=customer_id,
                plan=None,
                status="canceled",
                stripe_subscription_id=str(data.get("id") or "") or None,
            )

    return JSONResponse({"status": "ok"})


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


def generate_notes_payload(transcript: str, chapters: list) -> dict:
    return llm_providers.generate_notes(transcript, chapters)


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
