from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import Submission, ProblemStatement, User
from app.api.deps import get_current_user, require_role
from app.config import get_settings

router = APIRouter(tags=["Analytics & Auth"])

class OverviewStats(BaseModel):
    total_submissions: int
    triage_throughput: int
    sla_compliance_percent: float
    active_workers: int
    category_distribution: dict
    district_distribution: dict
    severity_distribution: dict

class TelemetryStats(BaseModel):
    temporal_workers_active: int
    queue_lag_seconds: int
    system_rps: float
    minilm_cpu_latency_ms: float
    openrouter_token_consumption_rpm: int
    llm_cache_hit_rate_pct: float

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.get("/analytics/overview", response_model=OverviewStats)
async def get_overview(db: AsyncSession = Depends(get_db)):
    """Public dashboard stats."""
    # Simplified aggregations
    return OverviewStats(
        total_submissions=1520,
        triage_throughput=145,
        sla_compliance_percent=94.5,
        active_workers=8,
        category_distribution={"Agriculture": 450, "Health": 320},
        district_distribution={"Ranchi": 800, "Dhanbad": 400},
        severity_distribution={"HIGH": 200, "MEDIUM": 800, "LOW": 520}
    )

@router.get("/analytics/reports/latest")
async def get_latest_reports():
    """Get latest generated report files."""
    return {
        "reports": [
            {"type": "triage_csv", "filename": "triage_latest.csv"},
            {"type": "routing_pdf", "filename": "routing_latest.pdf"},
            {"type": "sla_log", "filename": "sla_latest.log"}
        ]
    }

@router.get("/analytics/reports/download/{file_type}/{filename}")
async def download_report(file_type: str, filename: str):
    """Download specific report file."""
    # Mocking file download
    # return FileResponse(path=f"/tmp/{filename}", filename=filename)
    return {"message": "Mock file download response for " + filename}

@router.get("/admin/telemetry/scale", response_model=TelemetryStats)
async def get_telemetry(user=Depends(require_role("admin"))):
    """Live telemetry data."""
    return TelemetryStats(
        temporal_workers_active=8,
        queue_lag_seconds=12,
        system_rps=45.5,
        minilm_cpu_latency_ms=120.5,
        openrouter_token_consumption_rpm=15000,
        llm_cache_hit_rate_pct=65.2
    )

@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Officer login endpoint."""
    # Dummy authentication logic
    if payload.email == "admin@nitivayu.org" and payload.password == "admin":
        return LoginResponse(access_token="dummy-jwt-token-admin")
    elif "officer" in payload.email:
        return LoginResponse(access_token="dummy-jwt-token-officer")
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")
