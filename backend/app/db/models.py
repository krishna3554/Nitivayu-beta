from datetime import datetime, timezone
from typing import Optional, Any, List
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, LargeBinary, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector
import uuid

class Base(DeclarativeBase):
    pass

class Citizen(Base):
    __tablename__ = 'citizens'

    citizen_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    language_pref: Mapped[Optional[str]] = mapped_column(String(10), default='hi')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    submissions: Mapped[List["Submission"]] = relationship("Submission", back_populates="citizen")

class Submission(Base):
    __tablename__ = 'submissions'

    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizen_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('citizens.citizen_id', ondelete='SET NULL'), nullable=True)
    # Account-scoped ownership (WP-1): set when a signed-in citizen submits or
    # later claims an anonymous report via its tracking token. Anonymous
    # submissions stay NULL and remain trackable by token only.
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    geo_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geo_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geo_district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    geo_block: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # How the coordinates arrived: gps (device auto-detect) | manual (typed
    # or pin-corrected by the citizen) | district (no coordinates at all).
    geo_source: Mapped[str] = mapped_column(String(20), nullable=False, default='district')
    language_pref: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tracking_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default='INGESTED')
    # Optional self-declared reporter name (shown to officers/universities/CSR
    # on workspace views; contact details stay hashed — name only, no PII).
    reporter_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Optional opt-in contact for status notifications (mail/SMS). Plaintext
    # by necessity (hashed contacts cannot be dialed); only set with explicit
    # consent at intake. Production hardening: envelope-encrypt these columns.
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notify_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    citizen: Mapped[Optional["Citizen"]] = relationship("Citizen", back_populates="submissions")
    problem: Mapped[Optional["Problem"]] = relationship("Problem", back_populates="submission", uselist=False)

class Problem(Base):
    __tablename__ = 'problems'

    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('submissions.submission_id', ondelete='CASCADE'), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity_score: Mapped[Optional[int]] = mapped_column(Integer, CheckConstraint('severity_score BETWEEN 1 AND 5'), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    summary_embedding: Mapped[Optional[Any]] = mapped_column(Vector(384), nullable=True)
    assigned_officer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('problems.problem_id'), nullable=True)
    cluster_group_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='PENDING_OFFICER_REVIEW')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    submission: Mapped["Submission"] = relationship("Submission", back_populates="problem")
    route_assignments: Mapped[List["RouteAssignment"]] = relationship("RouteAssignment", back_populates="problem")
    project_teams: Mapped[List["ProjectTeam"]] = relationship("ProjectTeam", back_populates="problem")

class University(Base):
    __tablename__ = 'universities'

    university_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    iic_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    geo_lat: Mapped[float] = mapped_column(Float, nullable=False)
    geo_lng: Mapped[float] = mapped_column(Float, nullable=False)
    domain_specializations: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    active_capacity: Mapped[int] = mapped_column(Integer, default=10)
    current_load: Mapped[int] = mapped_column(Integer, default=0)
    capability_embedding: Mapped[Optional[Any]] = mapped_column(Vector(384), nullable=True)
    nodal_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    route_assignments: Mapped[List["RouteAssignment"]] = relationship("RouteAssignment", back_populates="university")

class RouteAssignment(Base):
    __tablename__ = 'route_assignments'

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('problems.problem_id', ondelete='CASCADE'), nullable=False)
    university_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('universities.university_id', ondelete='CASCADE'), nullable=False)
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='OFFERED')
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    problem: Mapped["Problem"] = relationship("Problem", back_populates="route_assignments")
    university: Mapped["University"] = relationship("University", back_populates="route_assignments")
    project_teams: Mapped[List["ProjectTeam"]] = relationship("ProjectTeam", back_populates="route_assignment")

class ProjectTeam(Base):
    __tablename__ = 'project_teams'

    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('route_assignments.assignment_id', ondelete='CASCADE'), nullable=True)
    problem_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('problems.problem_id', ondelete='CASCADE'), nullable=True)
    university_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('universities.university_id', ondelete='CASCADE'), nullable=True)
    faculty_mentor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    team_members: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    proposal_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    proposal_document_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='TEAM_FORMED')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    route_assignment: Mapped[Optional["RouteAssignment"]] = relationship("RouteAssignment", back_populates="project_teams")
    problem: Mapped[Optional["Problem"]] = relationship("Problem", back_populates="project_teams")
    milestones: Mapped[List["Milestone"]] = relationship("Milestone", back_populates="project_team")

class Milestone(Base):
    __tablename__ = 'milestones'

    milestone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('project_teams.team_id', ondelete='CASCADE'), nullable=True)
    milestone_num: Mapped[Optional[int]] = mapped_column(Integer, CheckConstraint('milestone_num IN (1, 2, 3)'), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='PENDING')
    evidence_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project_team: Mapped[Optional["ProjectTeam"]] = relationship("ProjectTeam", back_populates="milestones")

class Industry(Base):
    __tablename__ = 'industries'

    industry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    csr_focus_areas: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    csr_budget_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FundingLink(Base):
    __tablename__ = 'funding_links'

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('problems.problem_id', ondelete='CASCADE'), nullable=True)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('project_teams.team_id', ondelete='SET NULL'), nullable=True)
    industry_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('industries.industry_id', ondelete='CASCADE'), nullable=True)
    pledged_amount_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='PLEDGED')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Officer(Base):
    __tablename__ = 'officers'

    officer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(150), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = 'audit_logs'

    log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    before_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Phase-1 identity tables (nitivayu.md §6). Layered onto the existing schema;
# nothing above is modified. JWT claim shape is unchanged
# ({sub=user_id, role, organization_id}); only issuance gets rigorous.
# ---------------------------------------------------------------------------

class User(Base):
    """One account, exactly one workspace type (nitivayu.md §1.2)."""
    __tablename__ = 'users'

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Production note: these columns carry salted hashes for lookup plus
    # encrypted blobs would require envelope encryption (KMS/Fernet). Until a
    # KMS is wired, PII is stored as a one-way hash for lookup only — the
    # plaintext value is never persisted (see services/auth.py).
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    # Reversibly-encrypted phone for OPT-IN status SMS only (WP-9). Written at
    # OTP-verify time and only when PHONE_FERNET_KEY is configured; the
    # plaintext value is never logged. NULL = no SMS channel for this user.
    phone_enc: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Self-declared display name (signup/invite/OAuth). Shown in the navbar
    # and prefilled as reporter on intake; never used for auth decisions.
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    workspace_type: Mapped[str] = mapped_column(String(50), nullable=False, default='citizen')
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_pref: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # Opt-in SMS status updates (WP-9). Off by default; requires a reachable
    # contact channel (see services/auth.py PII note).
    notify_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class OtpCode(Base):
    """Single-use phone-OTP challenges (10-minute TTL, capped attempts)."""
    __tablename__ = 'otp_codes'

    otp_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default='sms')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MediaAsset(Base):
    """One-to-many evidence for a submission (photos + audio note).

    Generalizes the legacy singular `submissions.photo_url`: keep `photo_url`
    as the first-photo convenience field so existing consumers keep working.
    """
    __tablename__ = 'media_assets'

    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('submissions.submission_id', ondelete='CASCADE'), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # photo | audio
    storage_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderation_status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')  # pending | clean | flagged
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OrgInvite(Base):
    """Admin-issued invites binding an email to an organization workspace."""
    __tablename__ = 'org_invites'

    invite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    organization_type: Mapped[str] = mapped_column(String(50), nullable=False)  # university | industry
    organization_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')  # pending | accepted | expired | revoked
    invited_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProjectUpdate(Base):
    """University progress update on an active project (P4).

    Written by the university in plain, reassuring language. Surfaced to:
    - the university's own project timeline,
    - the citizen's /track/:token timeline (as activity entries),
    - officers (audit-visible, same query path as the detail view).
    Citizen SMS/push is a logged notification intent: citizen phone numbers
    are stored one-way hashed by design, so no contact channel exists until
    an explicit opt-in contact field is added (documented, not faked).
    """
    __tablename__ = 'project_updates'

    update_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('project_teams.team_id', ondelete='CASCADE'), nullable=False)
    problem_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('problems.problem_id', ondelete='CASCADE'), nullable=True)
    author_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    milestone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # M1 | M2 | M3 | general
    photo_urls: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CadenceConfig(Base):
    """Batch-triage cadence (one row, upserted by PUT /admin/triage/schedules)."""
    __tablename__ = 'cadence_configs'

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    active_cadence: Mapped[str] = mapped_column(String(50), nullable=False, default='weekly')
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False, default='0 0 * * 0')
    monthly_macro_cron: Mapped[str] = mapped_column(String(100), nullable=False, default='0 0 1 * *')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ThemeCentroid(Base):
    """WP-11: monthly mean embedding per category, recomputed by the macro
    workflow. Routing blends the problem↔centroid similarity into the theme
    factor so the matcher learns from officer-approved volume."""
    __tablename__ = 'theme_centroids'

    category: Mapped[str] = mapped_column(String(100), primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(384), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SeasonalWeight(Base):
    """WP-11: per-calendar-month routing weight adjustments (e.g. flood
    season boosts Water theme). Applied by the routing scorer on top of the
    base weights; the macro workflow refreshes them monthly."""
    __tablename__ = 'seasonal_weights'

    month: Mapped[int] = mapped_column(Integer, CheckConstraint('month BETWEEN 1 AND 12'), primary_key=True)
    theme_weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BatchRun(Base):
    """One on-demand or scheduled batch-triage execution (run history)."""
    __tablename__ = 'batch_runs'

    batch_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    cadence: Mapped[str] = mapped_column(String(50), nullable=False, default='weekly')
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='RUNNING')
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    csv_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportLike(Base):
    """One like on a public-feed report (civic feed).

    Voters are either signed-in accounts (`u:<sha256(sub)[:32]>`) or anonymous
    browser tokens (`a:<uuid hex>`) generated client-side and held in
    localStorage. The unique (problem_id, voter_key) pair makes like/unlike
    idempotent and double-voting impossible at the database level.
    """
    __tablename__ = 'report_likes'

    like_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    problem_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('problems.problem_id', ondelete='CASCADE'), nullable=False, index=True)
    voter_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint('problem_id', 'voter_key', name='uq_report_likes_voter'),)

