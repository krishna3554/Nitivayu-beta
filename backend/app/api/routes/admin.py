"""Admin control plane: organization invite management (§5.5, Phase 6).

Invite-only onboarding for university/CSR workspaces. Citizens always
self-serve and never need an invite. Invites are emailed when SMTP is
configured, otherwise the token is returned once for manual delivery.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, parse_uuid, require_role
from app.db.models import OrgInvite
from app.services import auth as auth_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    organization_type: str = Field(pattern="^(university|industry)$")
    organization_name: str | None = Field(default=None, max_length=255)


@router.post("/invites", status_code=status.HTTP_201_CREATED)
async def send_invite(
    payload: InviteRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
):
    try:
        invite, raw_token = await auth_svc.create_invite(
            db,
            email=payload.email,
            organization_type=payload.organization_type,
            organization_name=payload.organization_name,
            invited_by=user.get("user_id"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    # B2.13: never log the raw invite token (secret). When SMTP is configured
    # the invite is emailed and the token never appears in the API response;
    # otherwise it is returned once for the admin to copy into an email.
    from app.config import get_settings

    from app.services import notify as notify_svc

    emailed = False
    if notify_svc.email_configured():
        frontend = (get_settings().OAUTH_FRONTEND_BASE or "").rstrip("/")
        link = f"{frontend}/signup?invite={raw_token}"
        emailed = await notify_svc.send_email(
            invite.email,
            f"Join {invite.organization_name or 'Nitivayu'} on Nitivayu",
            f"You have been invited to the {invite.organization_type} workspace"
            f" ({invite.organization_name or 'Nitivayu'}).\n\n"
            f"Accept within 7 days: {link}\n\n"
            "Citizens never need an invite — this link is for institutional accounts only.",
        )
    logger.info("Invite %s issued to %s (%s)", invite.invite_id, invite.email, invite.organization_type)
    body = {
        "invite_id": str(invite.invite_id),
        "email": invite.email,
        "organization_type": invite.organization_type,
        "organization_name": invite.organization_name,
        "emailed": emailed,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
    }
    if not emailed:
        body["token"] = raw_token
    return body


@router.get("/invites")
async def list_invites(db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))):
    rows = (
        await db.execute(select(OrgInvite).order_by(OrgInvite.created_at.desc()).limit(100))
    ).scalars().all()
    return [
        {
            "invite_id": str(r.invite_id),
            "email": r.email,
            "organization_type": r.organization_type,
            "organization_name": r.organization_name,
            "status": r.status,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(
    invite_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
):
    invite = await db.get(OrgInvite, parse_uuid(invite_id, "invite_id"))
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.status = "revoked"
    await db.commit()
    return {"status": "revoked"}
