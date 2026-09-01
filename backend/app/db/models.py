from datetime import datetime, timezone
from typing import Optional, Any, List
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, LargeBinary, Text, CheckConstraint
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
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    geo_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geo_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geo_district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    geo_block: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default='INGESTED')
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
