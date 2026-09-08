"""Casefile + P4 update tests. DB-free: scripted FakeSession like test_auth."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")

import uuid  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import create_access_token, get_db  # noqa: E402
from app.db.models import MediaAsset, Problem, ProjectTeam, ProjectUpdate, RouteAssignment, Submission, University  # noqa: E402
from app.main import app  # noqa: E402


class FakeScalars:
    def __init__(self, rows=None):
        self._rows = rows or []

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return FakeScalars(self._rows)

    def all(self):
        return [(row,) for row in self._rows]


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


def make_client(session, role="officer", org="org-1"):
    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    token = create_access_token({"sub": "tester", "role": role, "organization_id": org})
    client = TestClient(app, raise_server_exceptions=False)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def teardown_function():
    app.dependency_overrides.clear()


def _problem():
    return Problem(
        problem_id=uuid.uuid4(),
        submission_id=uuid.uuid4(),
        title="T",
        summary="S",
        category="Water",
        severity_score=4,
        status="PENDING_OFFICER_REVIEW",
        created_at=datetime.now(timezone.utc),
    )


def test_officer_detail_returns_full_casefile():
    problem = _problem()
    submission = Submission(
        submission_id=problem.submission_id,
        raw_text="raw", language_pref="hi",
        geo_district="Ranchi", geo_block="Sadar",
        geo_lat=23.3, geo_lng=85.3, geo_source="gps",
        tracking_token="NITIVAYU-2026-JH-X1",
        status="PENDING_TRIAGE",
        created_at=datetime.now(timezone.utc),
    )

    class FakeDB:
        async def get(self, model, key):
            if model is Problem:
                return problem
            if model is Submission:
                return submission
            return None

        async def execute(self, *args, **kwargs):
            return FakeResult([])

        def add(self, obj):
            return None

        async def flush(self):
            return None

        async def commit(self):
            return None

    async def _override():
        yield FakeDB()

    app.dependency_overrides[get_db] = _override
    token = create_access_token({"sub": "o", "role": "officer"})
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        f"/api/v1/officer/problems/{problem.problem_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["submission"]["geo_source"] == "gps"
    assert body["submission"]["language_pref"] == "hi"
    assert body["media"] == [] and body["updates"] == []


def test_officer_detail_404_for_unknown():
    session = ScriptedSession([])
    client = make_client(session)

    async def _none(model, key):
        return None

    session.get = _none
    response = client.get(f"/api/v1/officer/problems/{uuid.uuid4()}")
    assert response.status_code == 404


def test_university_assignment_enforces_org_scope():
    assignment = RouteAssignment(
        assignment_id=uuid.uuid4(),
        problem_id=uuid.uuid4(),
        university_id=uuid.uuid4(),
        rank_order=1,
        match_score=0.9,
        score_breakdown={},
        sla_deadline=datetime.now(timezone.utc),
        status="OFFERED",
    )

    async def _get(model, key):
        if model is RouteAssignment:
            return assignment
        return None

    session = ScriptedSession([])
    session.get = _get
    client = make_client(session, role="university", org="some-other-org")
    response = client.get(f"/api/v1/university/assignments/{assignment.assignment_id}")
    assert response.status_code == 403


def test_team_update_post_and_list():
    team = ProjectTeam(
        team_id=uuid.uuid4(),
        problem_id=uuid.uuid4(),
        university_id=uuid.uuid4(),
        faculty_mentor_name="M",
        student_lead_name="L",
        status="IN_PROGRESS",
    )
    org = str(team.university_id)

    async def _get(model, key):
        if model is ProjectTeam:
            return team
        if model is University:
            return University(name="Uni", short_code="U", district="D", geo_lat=0.0, geo_lng=0.0,
                              domain_specializations=[], nodal_contact_email="x@y")
        from app.db.models import Problem as P, Submission as S
        if model is P:
            return None
        if model is S:
            return None
        return None

    created = {}

    class CaptureSession(ScriptedSession):
        def add(self, obj):
            super().add(obj)
            if isinstance(obj, ProjectUpdate):
                created["update"] = obj

    session = CaptureSession([])
    session.get = _get
    client = make_client(session, role="university", org=org)
    response = client.post(
        f"/api/v1/university/teams/{team.team_id}/updates",
        data={"note": "Baseline testing complete. Next: treatment plan.", "milestone": "M1"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["milestone"] == "M1"
    assert created["update"].note.startswith("Baseline testing")

    session2 = CaptureSession([])
    session2.get = _get
    client2 = make_client(session2, role="university", org=org)
    # list endpoint: one execute returning the created update
    session2._script = [FakeResult([created["update"]])]
    response2 = client2.get(f"/api/v1/university/teams/{team.team_id}/updates")
    assert response2.status_code == 200
    assert response2.json()[0]["note"].startswith("Baseline testing")


def test_media_missing_returns_404():
    session = ScriptedSession([])

    async def _none(model, key):
        return None

    session.get = _none
    client = make_client(session)
    response = client.get(f"/api/v1/media/{uuid.uuid4()}")
    assert response.status_code == 404
