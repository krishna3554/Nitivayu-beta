"""plan4 pipeline tests: meta/config, citizen linkage, escalations, milestones,
exports, industry, media review, macro activities, LLM cache, scoring weights.

DB-free FakeSession pattern (see test_casefile.py); file-writing exports land
in the test OUTPUT_ROOT and are cleaned up by teardown.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")

import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import create_access_token, get_db  # noqa: E402
from app.db.models import (  # noqa: E402
    FundingLink,
    MediaAsset,
    Milestone,
    Officer,
    Problem,
    ProjectTeam,
    RouteAssignment,
    Submission,
    University,
    User,
)
from app.main import app  # noqa: E402


class FakeScalars:
    def __init__(self, rows=None):
        self._rows = rows or []

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        return FakeScalars(self._rows)

    def all(self):
        return [(row,) for row in self._rows]

    def scalar_one(self):
        return self._scalar


class ScriptedSession:
    def __init__(self, script):
        self._script = list(script)
        self.added = []
        self.commits = 0

    async def execute(self, *args, **kwargs):
        assert self._script, "unexpected query: session script exhausted"
        return self._script.pop(0)

    async def get(self, model, key):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None


def make_client(session, role="citizen", sub=None, org=None):
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    token = create_access_token({"sub": sub or f"test-{role}", "role": role, "organization_id": org})
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def teardown_function():
    app.dependency_overrides.clear()


def _submission(**kwargs):
    defaults = dict(
        submission_id=uuid.uuid4(),
        raw_text="Handpump water is contaminated near the village well",
        tracking_token="NITIVAYU-2026-JH-T1",
        status="PENDING_TRIAGE",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Submission(**defaults)


def _problem(submission_id=None, **kwargs):
    defaults = dict(
        problem_id=uuid.uuid4(),
        submission_id=submission_id or uuid.uuid4(),
        title="Contaminated handpump",
        summary="Handpump water is contaminated",
        category="Water",
        severity_score=4,
        status="PENDING_OFFICER_REVIEW",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return Problem(**defaults)


# ---------------------------------------------------------------------------
# WP-2: meta/config
# ---------------------------------------------------------------------------

def test_meta_config_shape():
    client = make_client(ScriptedSession([]))
    response = client.get("/api/v1/meta/config")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["officer_sla_hours"] == 72
    assert body["university_sla_hours"] == 168
    assert body["score_weights"] == {"theme": 0.4, "semantic": 0.3, "capacity": 0.2, "geo": 0.1}
    assert len(body["districts"]) == 24
    assert "Water" in body["categories"]
    assert [m["code"] for m in body["milestone_structure"]] == ["M1", "M2", "M3"]


def test_demo_accounts_gated_off_by_default():
    client = make_client(ScriptedSession([]))
    response = client.get("/api/v1/meta/demo-accounts")
    assert response.status_code == 404


def test_demo_accounts_visible_when_enabled(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    try:
        client = make_client(ScriptedSession([]))
        response = client.get("/api/v1/meta/demo-accounts")
        assert response.status_code == 200, response.text
        assert len(response.json()["accounts"]) == 4
    finally:
        get_settings.cache_clear()


def test_public_stats_shape():
    session = ScriptedSession([
        FakeResult(scalar=3), FakeResult(scalar=1), FakeResult(scalar=2),
        FakeResult(scalar=150000.0), FakeResult(scalar=2),
    ])
    client = make_client(session)
    response = client.get("/api/v1/meta/public-stats")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_submissions"] == 3
    assert body["total_pledged_inr"] == 150000.0
    assert body["districts_covered"] == 2


# ---------------------------------------------------------------------------
# WP-1: citizen linkage + profile
# ---------------------------------------------------------------------------

class PairsResult:
    """Fake for multi-entity selects: .all() returns raw row tuples."""

    def __init__(self, pairs):
        self._pairs = pairs

    def all(self):
        return self._pairs


def test_citizen_reports_scoped_to_caller():
    owner = uuid.uuid4()
    submission = _submission(user_id=owner)
    problem = _problem(submission_id=submission.submission_id)
    assignment = RouteAssignment(
        assignment_id=uuid.uuid4(), problem_id=problem.problem_id, university_id=uuid.uuid4(),
        rank_order=1, match_score=0.9, score_breakdown={}, sla_deadline=datetime.now(timezone.utc), status="OFFERED",
    )
    assignment.university = University(name="BIT Mesra", short_code="B", district="Ranchi", geo_lat=0.0, geo_lng=0.0, domain_specializations=[])
    session = ScriptedSession([PairsResult([(submission, problem)]), FakeResult([assignment])])
    client = make_client(session, role="citizen", sub=str(owner))
    response = client.get("/api/v1/citizen/reports")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["tracking_token"] == submission.tracking_token
    assert body["items"][0]["matched_university"] == "BIT Mesra"


def test_citizen_reports_rejects_officer():
    client = make_client(ScriptedSession([]), role="officer", sub="o@x")
    assert client.get("/api/v1/citizen/reports").status_code == 403


def test_claim_links_anonymous_report():
    owner = uuid.uuid4()
    submission = _submission(user_id=None)

    async def _get(model, key):
        return None

    class GetSession(ScriptedSession):
        async def execute(self, *args, **kwargs):
            return FakeResult([submission])

    session = GetSession([])
    session.get = _get
    client = make_client(session, role="citizen", sub=str(owner))
    response = client.post("/api/v1/citizen/reports/claim", json={"tracking_token": submission.tracking_token})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "claimed"
    assert submission.user_id == owner


def test_claim_unknown_token_is_404():
    class GetSession(ScriptedSession):
        async def execute(self, *args, **kwargs):
            return FakeResult([])

    client = make_client(GetSession([]), role="citizen", sub=str(uuid.uuid4()))
    response = client.post("/api/v1/citizen/reports/claim", json={"tracking_token": "NITIVAYU-2026-JH-NOPE"})
    assert response.status_code == 404


def test_auth_me_roundtrip():
    owner = uuid.uuid4()
    user = User(user_id=owner, display_name="Ramesh", workspace_type="citizen", district="Ranchi",
                language_pref="hindi", notify_sms=True, is_verified=True)

    async def _get(model, key):
        if model is User:
            return user
        return None

    session = ScriptedSession([])
    session.get = _get
    client = make_client(session, role="citizen", sub=str(owner))
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Ramesh"
    assert response.json()["notify_sms"] is True

    response2 = client.patch("/api/v1/auth/me", json={"district": "Dhanbad", "notify_sms": False})
    assert response2.status_code == 200, response2.text
    assert user.district == "Dhanbad"
    assert user.notify_sms is False


def test_auth_me_patch_rejects_bad_language():
    owner = uuid.uuid4()

    async def _get(model, key):
        return User(user_id=owner, workspace_type="citizen") if model is User else None

    session = ScriptedSession([])
    session.get = _get
    client = make_client(session, role="citizen", sub=str(owner))
    assert client.patch("/api/v1/auth/me", json={"language_pref": "french"}).status_code == 422


# ---------------------------------------------------------------------------
# WP-3: escalations + queue shape
# ---------------------------------------------------------------------------

def _queue_problem():
    submission = _submission()
    problem = _problem(submission_id=submission.submission_id)
    problem.submission = submission
    assignment = RouteAssignment(
        assignment_id=uuid.uuid4(), problem_id=problem.problem_id, university_id=uuid.uuid4(),
        rank_order=1, match_score=0.9, score_breakdown={"theme": 1.0},
        sla_deadline=datetime.now(timezone.utc), status="PENDING_APPROVAL",
    )
    assignment.university = University(name="BIT Mesra", short_code="B", district="Ranchi", geo_lat=0.0, geo_lng=0.0, domain_specializations=[])
    problem.route_assignments = [assignment]
    return problem


def test_review_queue_returns_items_and_total():
    session = ScriptedSession([FakeResult(scalar=1), FakeResult([_queue_problem()])])
    client = make_client(session, role="officer", sub="o@x")
    response = client.get("/api/v1/officer/review-queue")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["top_matches"][0]["university_name"] == "BIT Mesra"


def test_escalations_flag_severity_and_reasons():
    problem = _queue_problem()
    problem.severity_score = 5
    problem.status = "PENDING_OFFICER_REVIEW"
    session = ScriptedSession([FakeResult([problem])])
    client = make_client(session, role="officer", sub="o@x")
    response = client.get("/api/v1/officer/escalations")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["reason"] == "SEVERITY_CRITICAL"


# ---------------------------------------------------------------------------
# WP-4/WP-5: accept creates team; milestone submit/verify
# ---------------------------------------------------------------------------

def test_accept_creates_team_and_milestones():
    uni_id = uuid.uuid4()
    assignment = RouteAssignment(
        assignment_id=uuid.uuid4(), problem_id=uuid.uuid4(), university_id=uni_id,
        rank_order=1, match_score=0.9, score_breakdown={}, sla_deadline=datetime.now(timezone.utc), status="OFFERED",
    )
    problem = _problem(submission_id=uuid.uuid4())
    problem.problem_id = assignment.problem_id

    async def _get(model, key):
        if model is RouteAssignment:
            return assignment
        if model is Problem:
            return problem
        if model is University:
            return University(university_id=uni_id, name="U", short_code="U", district="D",
                              geo_lat=0.0, geo_lng=0.0, domain_specializations=[], current_load=2)
        return None

    captured = {}

    class CaptureSession(ScriptedSession):
        def add(self, obj):
            super().add(obj)
            if isinstance(obj, ProjectTeam):
                captured["team"] = obj
            if isinstance(obj, Milestone):
                captured.setdefault("milestones", []).append(obj)

    session = CaptureSession([FakeResult([])])  # no existing team
    session.get = _get
    client = make_client(session, role="university", sub="u", org=str(uni_id))
    response = client.post(f"/api/v1/university/assignments/{assignment.assignment_id}/respond", json={"response": "ACCEPT"})
    assert response.status_code == 200, response.text
    assert assignment.status == "ACCEPTED"
    assert problem.status == "ACCEPTED"
    assert captured["team"].assignment_id == assignment.assignment_id
    assert sorted(m.milestone_num for m in captured["milestones"]) == [1, 2, 3]


def test_milestone_submit_and_verify_close_loop():
    uni_id = uuid.uuid4()
    team = ProjectTeam(team_id=uuid.uuid4(), problem_id=uuid.uuid4(), university_id=uni_id,
                       faculty_mentor_name="Prof", student_lead_name="Lead", status="TEAM_FORMED")
    milestone = Milestone(milestone_id=uuid.uuid4(), team_id=team.team_id, milestone_num=3,
                          title="M3 · Field Validation", due_date=datetime.now(timezone.utc), status="SUBMITTED")
    problem = _problem()
    problem.problem_id = team.problem_id
    submission = _submission()
    submission.submission_id = problem.submission_id

    async def _get(model, key):
        if model is Milestone:
            return milestone
        if model is ProjectTeam:
            return team
        if model is Problem:
            return problem
        if model is Submission:
            return submission
        if model is University:
            return University(university_id=uni_id, name="U", short_code="U", district="D",
                              geo_lat=0.0, geo_lng=0.0, domain_specializations=[], current_load=1)
        return None

    session = ScriptedSession([FakeResult([])])  # officer lookup: no officer row
    session.get = _get
    client = make_client(session, role="officer", sub="o@x")
    response = client.post(f"/api/v1/officer/milestones/{milestone.milestone_id}/verify",
                           json={"decision": "VERIFY", "comments": "Field visit done"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert milestone.status == "VERIFIED"
    assert body["problem_status"] == "COMPLETED"
    assert problem.status == "COMPLETED"
    assert submission.status == "COMPLETED"


def test_milestone_submit_sets_submitted():
    uni_id = uuid.uuid4()
    team = ProjectTeam(team_id=uuid.uuid4(), problem_id=uuid.uuid4(), university_id=uni_id,
                       faculty_mentor_name="Prof", student_lead_name="Lead", status="TEAM_FORMED")
    milestone = Milestone(milestone_id=uuid.uuid4(), team_id=team.team_id, milestone_num=1,
                          title="M1 · Feasibility Study", due_date=datetime.now(timezone.utc), status="PENDING")

    async def _get(model, key):
        if model is Milestone:
            return milestone
        if model is ProjectTeam:
            return team
        return None

    session = ScriptedSession([])
    session.get = _get
    client = make_client(session, role="university", sub="u", org=str(uni_id))
    response = client.post(f"/api/v1/university/milestones/{milestone.milestone_id}/submit", data={"note": "Survey done"})
    assert response.status_code == 200, response.text
    assert milestone.status == "SUBMITTED"


def test_team_patch_updates_details():
    uni_id = uuid.uuid4()
    team = ProjectTeam(team_id=uuid.uuid4(), problem_id=uuid.uuid4(), university_id=uni_id,
                       faculty_mentor_name="TBD", student_lead_name="TBD", status="TEAM_FORMED")

    async def _get(model, key):
        return team if model is ProjectTeam else None

    session = ScriptedSession([])
    session.get = _get
    client = make_client(session, role="university", sub="u", org=str(uni_id))
    response = client.patch(f"/api/v1/university/teams/{team.team_id}",
                            json={"faculty_mentor_name": "Prof. Sharma", "student_lead_name": "Priya"})
    assert response.status_code == 200, response.text
    assert team.faculty_mentor_name == "Prof. Sharma"


# ---------------------------------------------------------------------------
# WP-6/WP-7: exports, health, industry
# ---------------------------------------------------------------------------

def test_admin_export_kinds_and_download(tmp_path, monkeypatch):
    from app.services import outputs as outputs_mod

    monkeypatch.setattr(outputs_mod, "OUTPUT_ROOT", tmp_path)
    session = ScriptedSession([FakeResult([]), FakeResult([]), FakeResult([])])
    client = make_client(session, role="admin", sub="a@x")
    for kind in ("sla-log", "audit-jsonl", "csr-matrix"):
        response = client.post(f"/api/v1/admin/exports/{kind}")
        assert response.status_code == 200, (kind, response.text)
        assert response.json()["count"] == 0
    assert client.post("/api/v1/admin/exports/nope").status_code == 404


def test_admin_routing_pdf_export_writes_pdf(tmp_path, monkeypatch):
    from app.services import outputs as outputs_mod

    monkeypatch.setattr(outputs_mod, "OUTPUT_ROOT", tmp_path)
    session = ScriptedSession([FakeResult([]), FakeResult([])])
    client = make_client(session, role="admin", sub="a@x")
    response = client.post("/api/v1/admin/exports/routing-pdf")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["download_url"].endswith(".pdf")
    filename = body["download_url"].rsplit("/", 1)[-1]
    if not body["download_url"].startswith("http"):
        fetched = client.get(f"/api/v1/admin/exports/download/{filename}")
        assert fetched.status_code == 200
        assert fetched.content[:4] == b"%PDF"


def test_service_health_lists_services():
    client = make_client(ScriptedSession([FakeResult(scalar=0.0), FakeResult(scalar=0)]), role="admin", sub="a@x")
    response = client.get("/api/v1/admin/health/services")
    assert response.status_code == 200, response.text
    names = [s["name"] for s in response.json()["services"]]
    assert "Temporal Workflows" in names and "LLM Extraction" in names


def test_invites_list_and_industry_impact():
    session = ScriptedSession([FakeResult([])])
    client = make_client(session, role="admin", sub="a@x")
    assert client.get("/api/v1/admin/invites").status_code == 200

    session2 = ScriptedSession([FakeResult([]), FakeResult(scalar=0), FakeResult([])])
    org = uuid.uuid4()
    client2 = make_client(session2, role="industry", sub=str(org), org=str(org))
    response = client2.get("/api/v1/industry/impact")
    assert response.status_code == 200, response.text
    assert response.json()["projects_funded"] == 0


# ---------------------------------------------------------------------------
# WP-10: media review
# ---------------------------------------------------------------------------

def test_clear_flagged_media():
    asset = MediaAsset(asset_id=uuid.uuid4(), submission_id=uuid.uuid4(), kind="photo",
                       storage_url="/tmp/x", moderation_status="flagged")

    async def _get(model, key):
        return asset if model is MediaAsset else None

    session = ScriptedSession([])
    session.get = _get
    client = make_client(session, role="officer", sub="o@x")
    assert client.post(f"/api/v1/officer/media/{asset.asset_id}/clear").status_code == 200
    assert asset.moderation_status == "clean"
    assert client.post(f"/api/v1/officer/media/{asset.asset_id}/clear").status_code == 409


def test_media_sniff_labels():
    from app.activities.media import _sniff

    assert _sniff("photo", b"\xff\xd8\xff" + b"0" * 20) == "jpeg"
    assert _sniff("photo", b"RIFF1234WEBP") == "webp"
    assert _sniff("audio", b"\x1a\x45\xdf\xa3" + b"0" * 20) == "webm"
    assert _sniff("photo", b"NOTANIMAGE!!") is None


# ---------------------------------------------------------------------------
# WP-0/WP-2/WP-11: cache, weights, macro registration
# ---------------------------------------------------------------------------

def test_llm_cache_roundtrip_without_redis(monkeypatch):
    import asyncio

    from app.services import llm as llm_mod
    from app.services import redis_client as redis_mod

    monkeypatch.setattr(redis_mod, "get_redis", lambda: None)
    assert asyncio.run(llm_mod._cache_lookup("abc")) is None
    asyncio.run(llm_mod._cache_store("abc", {"title": "T"}))  # must not raise


def test_score_weights_match_settings():
    from app.activities.route import score_weights
    from app.config import get_settings

    settings = get_settings()
    assert score_weights() == {
        "theme": settings.SCORE_WEIGHT_THEME,
        "semantic": settings.SCORE_WEIGHT_SEMANTIC,
        "capacity": settings.SCORE_WEIGHT_CAPACITY,
        "geo": settings.SCORE_WEIGHT_GEO,
    }


def test_macro_workflow_references_registered_activities():
    import inspect

    import app.activities.macro as macro
    import app.workflows.monthly_macro as monthly

    registered = {
        "audit_officer_overrides_activity",
        "recompute_theme_centroid_embeddings_activity",
        "apply_seasonal_weight_adjustments_activity",
        "run_csr_matching_activity",
    }
    assert registered.issubset({name for name in dir(macro) if not name.startswith("_")})
    source = inspect.getsource(monthly)
    for name in registered | {"generate_csr_excel_export_activity"}:
        assert name in source
    # Old broken string-based references are gone (they bypass registration).
    assert '"audit_officer_overrides_activity"' not in source
