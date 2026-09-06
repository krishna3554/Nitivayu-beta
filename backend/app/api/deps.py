from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from app.config import get_settings
from app.db.session import get_db
from temporalio.client import Client

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=settings.JWT_EXPIRY_HOURS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return {"user_id": user_id, "role": role, "organization_id": payload.get("organization_id")}

async def get_current_user_optional(token: str | None = Depends(oauth2_scheme_optional)) -> dict | None:
    """Lenient variant for rate-limit keying and public endpoints: None when anonymous."""
    if not token:
        return None
    try:
        return await get_current_user(token)
    except HTTPException:
        return None

def require_role(*roles):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in roles:
            required = " or ".join(roles)
            raise HTTPException(
                status_code=403,
                detail=f"This portal requires a {required} account; you are signed in as '{current_user.get('role')}'.",
            )
        return current_user
    return role_checker


# Backend role -> frontend workspace namespace (nitivayu.md §1.3). Admins may
# preview any workspace; everyone else is confined to their own shell.
ROLE_WORKSPACE = {
    "citizen": "citizen",
    "officer": "officer",
    "admin": "admin",
    "university": "university",
    "industry": "corporate",
    "corporate": "corporate",
    "csr": "corporate",
}


def workspace_of(user: dict) -> str:
    explicit = (user.get("workspace_type") or "").lower()
    if explicit in {"citizen", "officer", "admin", "university", "corporate"}:
        return explicit
    return ROLE_WORKSPACE.get((user.get("role") or "").lower(), "citizen")


def require_workspace(*workspaces: str, org_scoped: bool = True):
    """Single RBAC+ABAC gate replacing per-route ad-hoc checks (§5.5).

    Admins pass any workspace gate (preview). Otherwise the caller's
    workspace must be listed. With org_scoped=True, university/industry
    callers must also carry an organization_id (mirrors the existing
    inbox/opportunity scoping as a hard invariant).
    """

    async def checker(current_user: dict = Depends(get_current_user)):
        workspace = workspace_of(current_user)
        # Admins preview any workspace; everyone else must be listed.
        if workspace != "admin" and workspace not in workspaces:
            allowed = ", ".join(workspaces)
            raise HTTPException(
                status_code=403,
                detail=f"This area belongs to the {allowed} workspace.",
            )
        if workspace == "admin":
            return current_user
        if org_scoped and workspace in {"university", "corporate"} and not current_user.get("organization_id"):
            raise HTTPException(status_code=403, detail="This account is not linked to an organization workspace")
        return current_user

    return checker

async def get_temporal_client(request: Request) -> Client:
    """Reuse the lifespan-managed client; connect per request only as a fallback."""
    client = getattr(request.app.state, "temporal_client", None)
    if client is not None:
        return client
    settings = get_settings()
    return await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)
