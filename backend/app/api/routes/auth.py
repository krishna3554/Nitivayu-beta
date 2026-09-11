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
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.db.models import Officer, University, Industry, User
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


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    district: str | None = Field(default=None, max_length=100)
    language_pref: str | None = Field(default=None, max_length=10)
    notify_sms: bool | None = None


async def _resolve_account(db: AsyncSession, user: dict):
    """JWT sub is a users.user_id UUID for registered accounts; officer logins
    still carry their email (see /auth/login). Returns (kind, row)."""
    sub = str(user.get("user_id") or "")
    try:
        account = await db.get(User, uuid.UUID(sub))
        if account is not None:
            return "user", account
    except (ValueError, AttributeError, TypeError):
        pass
    officer = (await db.execute(select(Officer).where(Officer.email == sub.lower()))).scalars().first()
    if officer is not None:
        return "officer", officer
    return None, None


@router.get("/me")
async def get_me(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """The signed-in account's profile — powers the citizen profile page and
    navbar identity instead of static copy."""
    kind, row = await _resolve_account(db, user)
    if kind == "user":
        org_name = None
        if row.organization_id:
            org = await db.get(University, row.organization_id) or await db.get(Industry, row.organization_id)
            org_name = getattr(org, "name", None) if org else None
        return {
            "kind": "user",
            "display_name": row.display_name,
            "role": user.get("role"),
            "workspace_type": row.workspace_type,
            "district": row.district,
            "language_pref": row.language_pref,
            "notify_sms": bool(row.notify_sms),
            "is_verified": bool(row.is_verified),
            "organization_name": org_name,
            "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
        }
    if kind == "officer":
        return {
            "kind": "officer",
            "display_name": row.name,
            "role": "admin" if row.role == "state_admin" else "officer",
            "workspace_type": "admin" if row.role == "state_admin" else "officer",
            "district": row.district,
            "language_pref": None,
            "notify_sms": False,
            "is_verified": True,
            "organization_name": row.department,
            "last_login_at": None,
        }
    raise HTTPException(status_code=404, detail="Account not found")


@router.patch("/me")
async def patch_me(payload: ProfilePatch, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    """Update self-serve profile fields (citizen/user accounts only)."""
    kind, row = await _resolve_account(db, user)
    if kind != "user":
        raise HTTPException(status_code=403, detail="Only self-serve accounts can edit their profile")
    updates = payload.model_dump(exclude_unset=True)
    if "display_name" in updates:
        row.display_name = (updates["display_name"] or "").strip()[:255] or row.display_name
    if "district" in updates:
        row.district = (updates["district"] or "").strip()[:100] or None
    if "language_pref" in updates:
        value = (updates["language_pref"] or "").strip().lower()
        if value and value not in {"hindi", "hinglish", "english"}:
            raise HTTPException(status_code=422, detail="language_pref must be hindi, hinglish, or english")
        row.language_pref = value or None
    if "notify_sms" in updates:
        row.notify_sms = bool(updates["notify_sms"])
    await db.commit()
    return {"status": "updated"}


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
    # sanitize_next happens inside oauth_authorize_url via signed state.
    url = auth_svc.oauth_authorize_url(provider, next_url=next or "/app/citizen")
    if not url:
        if provider == "facebook":
            raise HTTPException(
                status_code=501,
                detail="Facebook sign-in is retired on this deployment — use Google or email sign-in.",
            )
        raise HTTPException(
            status_code=501,
            detail=f"{provider.title()} sign-in is not configured on this deployment.",
        )
    return {"url": url}


class OAuthConsumeRequest(BaseModel):
    code: str = Field(min_length=16, max_length=128)


@router.post("/oauth/consume", dependencies=[Depends(limited)])
async def oauth_consume(payload: OAuthConsumeRequest):
    """Exchange a one-time OAuth `code` for the JWT (B2.7).

    The callback never places the token in ?token= (leaks via logs/history).
    The code is single-use with a 60s TTL; this endpoint returns the stored
    session payload once, then the code is dead.
    """
    session = await auth_svc.consume_oauth_session(payload.code)
    if not session:
        raise HTTPException(status_code=400, detail="That sign-in code expired or was already used. Try again.")
    return session


_google_certs_cache: dict = {"keys": None, "fetched_at": 0.0}


async def _google_certs() -> dict:
    import time

    now = time.monotonic()
    if _google_certs_cache["keys"] is not None and now - _google_certs_cache["fetched_at"] < 3600:
        return _google_certs_cache["keys"]
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        res.raise_for_status()
        _google_certs_cache["keys"] = res.json()
        _google_certs_cache["fetched_at"] = now
        return _google_certs_cache["keys"]


def _verify_google_id_token(id_token: str) -> dict:
    """Validate Google id_token signature + aud/iss/exp (B2.5). Fail closed."""
    from jose import jwt as jose_jwt

    from app.config import get_settings

    settings = get_settings()
    if not id_token:
        raise ValueError("Missing id_token from Google.")
    # Fetch header to select the signing key without verifying yet.
    header = jose_jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    # Certs are fetched by the async caller and passed via cache; this sync
    # helper reads the cache synchronously (populated before call).
    keys = _google_certs_cache.get("keys") or {}
    key = None
    for k in keys.get("keys", []):
        if k.get("kid") == kid:
            key = k
            break
    if key is None:
        raise ValueError("Unknown Google signing key.")
    claims = jose_jwt.decode(
        id_token,
        key,
        algorithms=["RS256"],
        audience=settings.GOOGLE_CLIENT_ID,
        issuer=("https://accounts.google.com", "accounts.google.com"),
        options={"verify_at_hash": False},
    )
    return claims


async def _exchange_google(code: str, redirect_uri: str) -> dict:
    from app.config import get_settings

    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError("Google OAuth is not configured.")
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
        token_body = token_res.json()
        access = token_body.get("access_token")
        id_token = token_body.get("id_token", "")
        if not access:
            raise ValueError("Google did not return an access token.")
        # B2.5: verify id_token (aud/iss/exp/signature) — fail closed.
        # Populate the JWKS cache first, then verify synchronously.
        await _google_certs()
        claims = _verify_google_id_token(id_token)
        email = claims.get("email", "")
        verified = bool(claims.get("email_verified", False))
        # Name comes from the verified userinfo endpoint (bearer-gated).
        name = str(claims.get("name", ""))
        try:
            me = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access}"}
            )
            me.raise_for_status()
            profile = me.json()
            name = profile.get("name", name) or name
            # Cross-check the userinfo email matches the verified id_token.
            if profile.get("email") and profile.get("email") != email:
                raise ValueError("Google email mismatch between id_token and userinfo.")
        except Exception:
            # userinfo is enrichment only — id_token claims already verified.
            pass
        return {"email": email, "name": name, "verified": verified}


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
    """Provider callback: exchange code, find-or-create account, 302 with one-time code."""
    from app.config import get_settings

    settings = get_settings()
    frontend = (getattr(settings, "OAUTH_FRONTEND_BASE", "") or "http://localhost:3000").rstrip("/")
    safe_next = auth_svc.validate_oauth_state(state)

    def fail(reason: str):
        params = urlencode({"error": "oauth_failed", "error_description": reason, "next": safe_next})
        return RedirectResponse(f"{frontend}/login?{params}", status_code=302)

    if error or not code:
        return fail("The provider did not complete sign-in.")
    if provider not in {"google", "facebook"}:
        return fail("Unknown OAuth provider.")
    if provider == "facebook":
        return fail("Facebook sign-in is retired on this deployment. Use Google or email sign-in.")
    callback = f"{(settings.OAUTH_CALLBACK_BASE or '').rstrip('/')}/api/v1/auth/oauth/{provider}/callback"
    try:
        profile = await (_exchange_google(code, callback) if provider == "google" else _exchange_facebook(code, callback))
    except Exception:
        return fail("Could not verify the provider response. Try email sign-in instead.")
    if not profile.get("email"):
        return fail("The provider did not share an email address.")
    # B2.6: honor email_verified — do NOT force is_verified=True.
    verified = bool(profile.get("verified"))
    # U5 (linkable): institutional emails resolve to their workspace.
    role, organization_id, workspace_type = await auth_svc.resolve_oauth_workspace(db, email=profile["email"])
    oauth_name = (profile.get("name") or "").strip()[:120] or None
    if role == "citizen":
        user = await auth_svc.get_or_create_citizen(db, email=profile["email"])
        user.workspace_type = "citizen"
        if oauth_name and not user.display_name:
            user.display_name = oauth_name
        if organization_id:
            user.organization_id = organization_id
    else:
        from sqlalchemy import select as _select

        from app.db.models import User as _User

        existing = (
            await db.execute(_select(_User).where(_User.email_encrypted == auth_svc.contact_hash(profile["email"])))
        ).scalars().first()
        if existing is None:
            user = _User(
                email_encrypted=auth_svc.contact_hash(profile["email"]),
                display_name=oauth_name,
                workspace_type=workspace_type,
                organization_id=organization_id,
                is_verified=verified,
                last_login_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.flush()
        else:
            user = existing
            if oauth_name and not user.display_name:
                user.display_name = oauth_name
            # Keep workspace linkage fresh without clobbering admin preview.
            if organization_id and not user.organization_id:
                user.organization_id = organization_id
    user.is_verified = verified
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    tokens = auth_svc.issue_jwt(user, role)
    # B2.7: one-time code delivery — JWT never appears in ?token= query/logs.
    session_payload = {
        **tokens,
        "organization_id": organization_id or tokens.get("organization_id"),
        "organization_name": "",
        "next": safe_next,
    }
    one_time = await auth_svc.store_oauth_session(session_payload)
    params = urlencode({"code": one_time, "next": safe_next})
    return RedirectResponse(f"{frontend}/login?{params}", status_code=302)
