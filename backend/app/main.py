import base64
import hashlib
import hmac
import json
import os
import secrets
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
from .db.integrations_repository import IntegrationsRepository
from .db.team_repository import TeamRepository
from .db.referral_repository import ReferralRepository
from .db.models import JobModel, TeamRole
from .llm import providers as llm_providers
from .llm.study_tools import build_chat_answer, normalize_study_pack

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


async def require_team_access(
    repo: TeamRepository,
    team_id: uuid.UUID,
    user_id: str | None,
    email: str | None,
    admin_required: bool = False,
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub claim")
    team = await repo.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if team.owner_user_id == user_id:
        return team

    member = await repo.get_member_for_user(team_id, user_id, email)
    if not member:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if admin_required and member.role != TeamRole.ADMIN:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return team


def get_price_id_for_plan(plan: str) -> str:
    if plan == "student":
        return os.getenv("STRIPE_STUDENT_PRICE_ID", "")
    if plan == "pro":
        return os.getenv("STRIPE_PRO_PRICE_ID", "")
    if plan == "team":
        return os.getenv("STRIPE_TEAM_PRICE_ID", "")
    return ""


def map_price_id_to_plan(price_id: str) -> Optional[str]:
    student_price = os.getenv("STRIPE_STUDENT_PRICE_ID", "")
    pro_price = os.getenv("STRIPE_PRO_PRICE_ID", "")
    team_price = os.getenv("STRIPE_TEAM_PRICE_ID", "")
    if student_price and price_id == student_price:
        return "student"
    if pro_price and price_id == pro_price:
        return "pro"
    if team_price and price_id == team_price:
        return "team"
    return None


def generate_api_key() -> tuple[str, str, str]:
    raw_key = f"vs_{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, key_prefix, key_hash


def generate_webhook_secret() -> str:
    return secrets.token_urlsafe(32)


@app.get("/api/v1/lti/config")
async def get_lti_config():
    issuer = os.getenv("LTI_ISSUER", "")
    client_id = os.getenv("LTI_CLIENT_ID", "")
    auth_login_url = os.getenv("LTI_AUTH_LOGIN_URL", "")
    redirect_url = os.getenv("LTI_REDIRECT_URL", "")
    jwks_url = os.getenv("LTI_JWKS_URL", "")

    return JSONResponse({
        "issuer": issuer,
        "client_id": client_id,
        "auth_login_url": auth_login_url,
        "redirect_url": redirect_url,
        "jwks_url": jwks_url,
    })


@app.get("/api/v1/lti/jwks")
async def get_lti_jwks():
    return JSONResponse({"keys": []})


@app.get("/api/v1/optimization/config")
async def get_cost_optimization_config():
    enabled = os.getenv("COST_OPT_ENABLED", "false").lower() == "true"
    model = os.getenv("COST_OPT_MODEL", "")
    provider = os.getenv("COST_OPT_PROVIDER", "")
    return JSONResponse({
        "enabled": enabled,
        "model": model,
        "provider": provider,
    })


@app.post("/api/v1/lti/launch")
async def lti_launch(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    id_token = body.get("id_token")
    if not id_token:
        return JSONResponse({"error": "Missing id_token"}, status_code=400)

    return JSONResponse({"status": "ok"})


@app.post("/api/v1/referrals/code", status_code=201)
async def create_referral_code(
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

    repo = ReferralRepository(db)
    record = await repo.create_or_get_code(user_id)
    return JSONResponse({"code": record.code}, status_code=201)


@app.get("/api/v1/referrals/code")
async def get_referral_code(
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

    repo = ReferralRepository(db)
    record = await repo.get_code_for_user(user_id)
    if not record:
        return JSONResponse({"error": "Referral code not found"}, status_code=404)
    return JSONResponse({"code": record.code})


@app.post("/api/v1/referrals/redeem")
async def redeem_referral(
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

    code = str(body.get("code") or "").strip()
    if not code:
        return JSONResponse({"error": "Missing code"}, status_code=400)

    repo = ReferralRepository(db)
    code_record = await repo.get_code_by_value(code)
    if not code_record:
        return JSONResponse({"error": "Invalid referral code"}, status_code=404)

    if code_record.user_id == user_id:
        return JSONResponse({"error": "Cannot redeem own code"}, status_code=400)

    existing = await repo.get_redemption_for_user(user_id)
    if existing:
        return JSONResponse({"error": "Referral already redeemed"}, status_code=400)

    await repo.record_redemption(code_record.user_id, user_id, code)
    await repo.add_bonus_minutes(code_record.user_id, 60)
    await repo.add_bonus_minutes(user_id, 60)

    return JSONResponse({"referrer_bonus": 60, "referred_bonus": 60})


@app.get("/api/v1/referrals/credits")
async def get_referral_credits(
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

    repo = ReferralRepository(db)
    record = await repo.get_credit(user_id)
    return JSONResponse({"bonus_minutes": record.bonus_minutes if record else 0})


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


@app.get("/api/v1/teams")
async def list_teams(
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
    email = claims.get("email")
    repo = TeamRepository(db)
    teams = await repo.list_teams_for_user(user_id, email)
    return JSONResponse({
        "items": [
            {
                "id": str(team.id),
                "name": team.name,
                "plan": team.plan,
                "seat_count": team.seat_count,
                "billing_status": team.billing_status,
            }
            for team in teams
        ]
    })


@app.post("/api/v1/teams", status_code=201)
async def create_team(
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

    name = str(body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "Missing team name"}, status_code=400)

    seat_count = int(body.get("seat_count") or 3)
    seat_count = max(1, seat_count)

    repo = TeamRepository(db)
    team = await repo.create_team(owner_user_id=user_id, name=name, seat_count=seat_count)

    return JSONResponse(
        {
            "id": str(team.id),
            "name": team.name,
            "plan": team.plan,
            "seat_count": team.seat_count,
            "billing_status": team.billing_status,
        },
        status_code=201,
        headers={"Location": f"/api/v1/teams/{team.id}"},
    )


@app.get("/api/v1/teams/{team_id}")
async def get_team(
    team_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        team = await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return JSONResponse({
        "id": str(team.id),
        "name": team.name,
        "plan": team.plan,
        "seat_count": team.seat_count,
        "billing_status": team.billing_status,
        "branding": team.branding_json,
    })


@app.get("/api/v1/teams/{team_id}/members")
async def list_team_members(
    team_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    members = await repo.list_members(team_uuid)
    return JSONResponse({
        "items": [
            {
                "id": str(member.id),
                "email": member.email,
                "role": member.role.value,
                "status": member.status,
                "user_id": member.user_id,
            }
            for member in members
        ]
    })


@app.post("/api/v1/teams/{team_id}/members", status_code=201)
async def add_team_member(
    team_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
            admin_required=True,
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    try:
        body = await request.json()
    except Exception:
        body = {}

    email = str(body.get("email") or "").strip().lower()
    if not email:
        return JSONResponse({"error": "Missing email"}, status_code=400)

    role_value = str(body.get("role") or "member").lower()
    try:
        role = TeamRole(role_value)
    except ValueError:
        return JSONResponse({"error": "Invalid role"}, status_code=400)

    member = await repo.add_member(team_uuid, email=email, role=role)
    return JSONResponse(
        {
            "id": str(member.id),
            "email": member.email,
            "role": member.role.value,
            "status": member.status,
        },
        status_code=201,
    )


@app.patch("/api/v1/teams/{team_id}/members/{member_id}")
async def update_team_member(
    team_id: str,
    member_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        return JSONResponse({"error": "Invalid ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
            admin_required=True,
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    try:
        body = await request.json()
    except Exception:
        body = {}

    role_value = str(body.get("role") or "").lower()
    if not role_value:
        return JSONResponse({"error": "Missing role"}, status_code=400)
    try:
        role = TeamRole(role_value)
    except ValueError:
        return JSONResponse({"error": "Invalid role"}, status_code=400)

    member = await repo.update_member_role(member_uuid, role)
    if not member:
        return JSONResponse({"error": "Member not found"}, status_code=404)

    return JSONResponse({
        "id": str(member.id),
        "email": member.email,
        "role": member.role.value,
        "status": member.status,
    })


@app.delete("/api/v1/teams/{team_id}/members/{member_id}")
async def remove_team_member(
    team_id: str,
    member_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
        member_uuid = uuid.UUID(member_id)
    except ValueError:
        return JSONResponse({"error": "Invalid ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
            admin_required=True,
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    removed = await repo.remove_member(member_uuid)
    if not removed:
        return JSONResponse({"error": "Member not found"}, status_code=404)
    return JSONResponse({"status": "removed"})


@app.get("/api/v1/teams/{team_id}/collections")
async def list_collections(
    team_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    collections = await repo.list_collections(team_uuid)
    return JSONResponse({
        "items": [
            {
                "id": str(collection.id),
                "name": collection.name,
                "description": collection.description,
                "created_by": collection.created_by,
            }
            for collection in collections
        ]
    })


@app.post("/api/v1/teams/{team_id}/collections", status_code=201)
async def create_collection(
    team_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
            admin_required=True,
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    try:
        body = await request.json()
    except Exception:
        body = {}

    name = str(body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "Missing name"}, status_code=400)
    description = body.get("description")

    collection = await repo.create_collection(
        team_id=team_uuid,
        name=name,
        description=description,
        created_by=claims.get("sub") or "",
    )

    return JSONResponse(
        {
            "id": str(collection.id),
            "name": collection.name,
            "description": collection.description,
            "created_by": collection.created_by,
        },
        status_code=201,
    )


@app.get("/api/v1/teams/{team_id}/sso")
async def get_team_sso(
    team_id: str,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    record = await repo.get_sso_provider(team_uuid)
    if not record:
        return JSONResponse({"provider": None, "domain": None, "client_id": None, "is_enabled": False})

    return JSONResponse({
        "provider": record.provider,
        "domain": record.domain,
        "client_id": record.client_id,
        "is_enabled": record.is_enabled,
    })


@app.put("/api/v1/teams/{team_id}/sso")
async def update_team_sso(
    team_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = require_auth(authorization)
    except (PermissionError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    try:
        team_uuid = uuid.UUID(team_id)
    except ValueError:
        return JSONResponse({"error": "Invalid team ID"}, status_code=400)

    repo = TeamRepository(db)
    try:
        await require_team_access(
            repo,
            team_uuid,
            claims.get("sub"),
            claims.get("email"),
            admin_required=True,
        )
    except HTTPException as exc:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    try:
        body = await request.json()
    except Exception:
        body = {}

    provider = str(body.get("provider") or "").strip().lower()
    domain = str(body.get("domain") or "").strip().lower()
    client_id = str(body.get("client_id") or "").strip()
    is_enabled = bool(body.get("is_enabled", False))

    if not provider:
        return JSONResponse({"error": "Missing provider"}, status_code=400)
    if not domain:
        return JSONResponse({"error": "Missing domain"}, status_code=400)

    record = await repo.upsert_sso_provider(
        team_id=team_uuid,
        provider=provider,
        domain=domain,
        client_id=client_id or None,
        is_enabled=is_enabled,
    )

    return JSONResponse({
        "provider": record.provider,
        "domain": record.domain,
        "client_id": record.client_id,
        "is_enabled": record.is_enabled,
    })


@app.get("/api/v1/api-keys")
async def list_api_keys(
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

    repo = IntegrationsRepository(db)
    keys = await repo.list_api_keys(user_id)
    return JSONResponse({
        "items": [
            {
                "id": str(item.id),
                "label": item.label,
                "key_prefix": item.key_prefix,
                "team_id": str(item.team_id) if item.team_id else None,
                "is_active": item.is_active,
                "created_at": item.created_at.isoformat(),
                "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
            }
            for item in keys
        ]
    })


@app.post("/api/v1/api-keys", status_code=201)
async def create_api_key(
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

    label = str(body.get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "Missing label"}, status_code=400)

    team_id_value = body.get("team_id")
    team_id = None
    if team_id_value:
        try:
            team_id = uuid.UUID(str(team_id_value))
        except ValueError:
            return JSONResponse({"error": "Invalid team ID"}, status_code=400)

        team_repo = TeamRepository(db)
        try:
            await require_team_access(
                team_repo,
                team_id,
                claims.get("sub"),
                claims.get("email"),
                admin_required=True,
            )
        except HTTPException as exc:
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    raw_key, key_prefix, key_hash = generate_api_key()
    repo = IntegrationsRepository(db)
    record = await repo.create_api_key(
        user_id=user_id,
        label=label,
        key_prefix=key_prefix,
        key_hash=key_hash,
        team_id=team_id,
    )

    return JSONResponse(
        {
            "id": str(record.id),
            "label": record.label,
            "key_prefix": record.key_prefix,
            "team_id": str(record.team_id) if record.team_id else None,
            "key": raw_key,
        },
        status_code=201,
    )


@app.delete("/api/v1/api-keys/{key_id}")
async def delete_api_key(
    key_id: str,
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
        key_uuid = uuid.UUID(key_id)
    except ValueError:
        return JSONResponse({"error": "Invalid key ID"}, status_code=400)

    repo = IntegrationsRepository(db)
    removed = await repo.delete_api_key(key_uuid, user_id)
    if not removed:
        return JSONResponse({"error": "API key not found"}, status_code=404)
    return JSONResponse({"status": "deleted"})


@app.get("/api/v1/webhooks")
async def list_webhooks(
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

    repo = IntegrationsRepository(db)
    webhooks = await repo.list_webhooks(user_id)
    return JSONResponse({
        "items": [
            {
                "id": str(hook.id),
                "url": hook.url,
                "events": hook.events,
                "team_id": str(hook.team_id) if hook.team_id else None,
                "is_active": hook.is_active,
            }
            for hook in webhooks
        ]
    })


@app.post("/api/v1/webhooks", status_code=201)
async def create_webhook(
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

    url = str(body.get("url") or "").strip()
    if not url:
        return JSONResponse({"error": "Missing webhook URL"}, status_code=400)

    events = body.get("events")
    if not isinstance(events, list) or not events:
        return JSONResponse({"error": "Missing events"}, status_code=400)
    events = [str(item).strip() for item in events if str(item).strip()]
    if not events:
        return JSONResponse({"error": "Missing events"}, status_code=400)

    team_id_value = body.get("team_id")
    team_id = None
    if team_id_value:
        try:
            team_id = uuid.UUID(str(team_id_value))
        except ValueError:
            return JSONResponse({"error": "Invalid team ID"}, status_code=400)

        team_repo = TeamRepository(db)
        try:
            await require_team_access(
                team_repo,
                team_id,
                claims.get("sub"),
                claims.get("email"),
                admin_required=True,
            )
        except HTTPException as exc:
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    secret = generate_webhook_secret()
    repo = IntegrationsRepository(db)
    hook = await repo.create_webhook(
        user_id=user_id,
        url=url,
        events=events,
        secret=secret,
        team_id=team_id,
    )

    return JSONResponse(
        {
            "id": str(hook.id),
            "url": hook.url,
            "events": hook.events,
            "team_id": str(hook.team_id) if hook.team_id else None,
            "secret": secret,
        },
        status_code=201,
    )


@app.delete("/api/v1/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
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
        webhook_uuid = uuid.UUID(webhook_id)
    except ValueError:
        return JSONResponse({"error": "Invalid webhook ID"}, status_code=400)

    repo = IntegrationsRepository(db)
    removed = await repo.delete_webhook(webhook_uuid, user_id)
    if not removed:
        return JSONResponse({"error": "Webhook not found"}, status_code=404)
    return JSONResponse({"status": "deleted"})


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
    if plan not in {"student", "pro", "team"}:
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


@app.post("/api/v1/billing/student/verify")
async def start_student_verification(
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

    reference_id = str(uuid.uuid4())
    billing_repo = BillingRepository(db)
    record = await billing_repo.create_student_verification(user_id, reference_id=reference_id)

    verification_url = os.getenv("SHEERID_VERIFICATION_URL", "")
    return JSONResponse({
        "status": record.status,
        "reference_id": record.reference_id,
        "verification_url": verification_url,
    })


@app.get("/api/v1/billing/student/status")
async def get_student_verification_status(
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

    billing_repo = BillingRepository(db)
    record = await billing_repo.get_student_verification(user_id)
    if not record:
        return JSONResponse({"status": "not_started"})

    return JSONResponse({
        "status": record.status,
        "reference_id": record.reference_id,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
    })


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

    transcript = str(body.get("transcript") or body.get("metadata", {}).get("transcript") or "").strip()
    notes_markdown = str(body.get("notes_markdown") or body.get("metadata", {}).get("notes_markdown") or "").strip()
    sections = body.get("sections") if isinstance(body.get("sections"), list) else []
    chat_payload = build_chat_answer(question, transcript, notes_markdown=notes_markdown, sections=sections)

    return JSONResponse({
        "answer": chat_payload["answer"],
        "citations": chat_payload["citations"],
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


def generate_notes_payload(
    transcript: str,
    chapters: list,
    style: str = "student_notes",
    output_language: str = "en",
    source_title: str | None = None,
    source_url: str | None = None,
) -> dict:
    payload = llm_providers.generate_notes(transcript, chapters, style=style, output_language=output_language)
    return normalize_study_pack(
        payload,
        transcript=transcript,
        chapters=chapters,
        style=style,
        output_language=output_language,
        source_title=source_title,
        source_url=source_url,
    )


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

    transcript = str(body.get("transcript") or "").strip()
    if not transcript:
        return JSONResponse({"error": "Missing transcript."}, status_code=400)

    chapters = body.get("chapters") if isinstance(body.get("chapters"), list) else []
    style = str(body.get("style") or body.get("summary_style") or "student_notes").strip() or "student_notes"
    output_language = str(body.get("output_language") or body.get("outputLanguage") or "en").strip() or "en"
    source_title = str(body.get("source_title") or body.get("sourceTitle") or "").strip() or None
    source_url = str(body.get("source_url") or body.get("sourceUrl") or "").strip() or None

    try:
        payload = generate_notes_payload(
            transcript,
            chapters,
            style=style,
            output_language=output_language,
            source_title=source_title,
            source_url=source_url,
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse(payload)
