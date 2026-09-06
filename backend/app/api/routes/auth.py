"""Public auth surface: citizen self-serve + institutional invites + social login.

Contracts match the frontend workspace model (nitivayu.md §4.3):
- POST /auth/register        citizen email signup -> JWT (auto-login)
- POST /auth/request-otp     citizen phone OTP challenge
- POST /auth/verify-otp      citizen phone OTP verify -> JWT
- POST /auth/accept-invite   institutional invite -> account (then /login)
- GET  /auth/oauth/{p}/url   provider authorization URL (501 until configured)
- GET  /auth/oauth/{p}/callback  provider callback -> 302 to frontend login

All auth endpoints are rate-limited (auth budget, per IP/account).
"""

from urllib.parse import urlencode
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.services import auth as auth_svc
from app.services.rate_limit import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
limited = rate_limit(setting="RATE_LIMIT_AUTH_PER_MIN")


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    district: str | None = Field(default=None, max_length=100)


class OtpRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    district: str | None = Field(default=None, max_length=100)


class OtpVerify(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class InviteAccept(BaseModel):
    token: str
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(limited)])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_svc.register_email(
            db, name=payload.name, email=payload.email, password=payload.password, district=payload.district
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return auth_svc.issue_jwt(user, "citizen")


@router.post("/request-otp", dependencies=[Depends(limited)])
async def request_otp(payload: OtpRequest, db: AsyncSession = Depends(get_db)):
    from app.config import get_settings

    phone = auth_svc.normalize_phone(payload.phone)
    if not auth_svc.valid_phone(phone):
        raise HTTPException(status_code=422, detail="Enter a valid phone number.")
    try:
        user, otp, code = await auth_svc.request_otp(db, phone=phone, district=payload.district)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    await db.commit()
    body: dict = {"sent": True, "expires_in": get_settings().OTP_TTL_SECONDS}
    # Demo escape hatch only — never enabled in production (see config).
    if get_settings().ALLOW_DEV_OTP:
        body["dev_code"] = code
    return body


@router.post("/verify-otp", dependencies=[Depends(limited)])
async def verify_otp(payload: OtpVerify, db: AsyncSession = Depends(get_db)):
    phone = auth_svc.normalize_phone(payload.phone)
    try:
        user = await auth_svc.verify_otp(db, phone=phone, code=payload.code)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        await db.commit()  # persist attempt counter / consumption
        raise HTTPException(status_code=401, detail=str(exc))
    await db.commit()
    return auth_svc.issue_jwt(user, "citizen")


@router.post("/accept-invite", dependencies=[Depends(limited)])
async def accept_invite(payload: InviteAccept, db: AsyncSession = Depends(get_db)):
    try:
        user, role = await auth_svc.accept_invite(
            db, token=payload.token, email=payload.email, name=payload.name, password=payload.password
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        await db.commit()
        raise HTTPException(status_code=410, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    # Also hand back a token so future clients can skip the extra login hop.
    return {"status": "accepted", **auth_svc.issue_jwt(user, role)}


@router.get("/oauth/{provider}/url", dependencies=[Depends(limited)])
async def oauth_url(provider: str, next: str = Query(default="/app/citizen")):
    if provider not in {"google", "facebook"}:
        raise HTTPException(status_code=404, detail="Unknown OAuth provider.")
    url = auth_svc.oauth_authorize_url(provider, next_url=next)
    if not url:
        raise HTTPException(
            status_code=501,
            detail=f"{provider.title()} sign-in is not configured on this deployment.",
        )
    return {"url": url}


async def _exchange_google(code: str, redirect_uri: str) -> dict:
    from app.config import get_settings

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_res.raise_for_status()
        access = token_res.json()["access_token"]
        me = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access}"}
        )
        me.raise_for_status()
        profile = me.json()
        return {"email": profile.get("email"), "name": profile.get("name", ""), "verified": profile.get("email_verified", False)}


async def _exchange_facebook(code: str, redirect_uri: str) -> dict:
    from app.config import get_settings

    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        token_res = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "client_id": settings.FACEBOOK_APP_ID,
                "client_secret": settings.FACEBOOK_APP_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        token_res.raise_for_status()
        access = token_res.json()["access_token"]
        me = await client.get(
            "https://graph.facebook.com/me",
            params={"fields": "id,name,email", "access_token": access},
        )
        me.raise_for_status()
        profile = me.json()
        return {"email": profile.get("email"), "name": profile.get("name", ""), "verified": bool(profile.get("email"))}


@router.get("/oauth/{provider}/callback", dependencies=[Depends(limited)])
async def oauth_callback(
    provider: str,
    code: str = Query(default=""),
    state: str = Query(default="/app/citizen"),
    error: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Provider callback: exchange code, find-or-create citizen, 302 to login."""
    from app.config import get_settings

    settings = get_settings()
    frontend = (getattr(settings, "OAUTH_FRONTEND_BASE", "") or "http://localhost:3000").rstrip("/")

    def fail(reason: str):
        params = urlencode({"error": "oauth_failed", "error_description": reason, "next": state})
        return RedirectResponse(f"{frontend}/login?{params}", status_code=302)

    if error or not code:
        return fail("The provider did not complete sign-in.")
    if provider not in {"google", "facebook"}:
        return fail("Unknown OAuth provider.")
    callback = f"{settings.OAUTH_CALLBACK_BASE.rstrip('/')}/api/v1/auth/oauth/{provider}/callback"
    try:
        profile = await (_exchange_google(code, callback) if provider == "google" else _exchange_facebook(code, callback))
    except Exception:
        return fail("Could not verify the provider response. Try email sign-in instead.")
    if not profile.get("email"):
        return fail("The provider did not share an email address.")
    user = await auth_svc.get_or_create_citizen(db, email=profile["email"])
    user.is_verified = True
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    tokens = auth_svc.issue_jwt(user, "citizen")
    params = urlencode(
        {
            "token": tokens["access_token"],
            "role": "citizen",
            "org": "",
            "next": state if state.startswith("/") else "/app/citizen",
        }
    )
    return RedirectResponse(f"{frontend}/login?{params}", status_code=302)
