"""Batch-triage control-plane tests. DB-free: scripted fakes like test_auth."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-pytest-only")

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import create_access_token, get_db, get_temporal_client  # noqa: E402
from app.db.models import BatchRun, CadenceConfig  # noqa: E402
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

    def scalar_one(self):
        return 0


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


class FakeTemporal:
    def __init__(self):
        self.started = []
        self.schedules_created = []

    async def start_workflow(self, workflow, args=None, id=None, task_queue=None, **kwargs):
        self.started.append({"workflow": workflow, "args": args, "id": id, "task_queue": task_queue})
        return None

    def get_workflow_handle(self, workflow_id):
        raise RuntimeError("not found")

    def get_schedule_handle(self, schedule_id):
        raise RuntimeError("no schedule")

    async def create_schedule(self, schedule_id, schedule, **kwargs):
        self.schedules_created.append(schedule_id)
        return None


def officer_client(session, temporal=None):
    async def _db():
        yield session

    async def _temporal():
        return temporal or FakeTemporal()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_temporal_client] = _temporal
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _officer_headers():
    token = create_access_token({"sub": "officer@nitivayu.gov.in", "role": "officer"})
    return {"Authorization": f"Bearer {token}"}


def test_batch_routes_registered(_clear_overrides):
    # FastAPI >=0.141 keeps includes lazy (_IncludedRouter), so assert at the
    # HTTP layer: every batch path must route (not 404/405).
    temporal = FakeTemporal()
    client = officer_client(ScriptedSession([FakeResult([]), FakeResult([]), FakeResult([])]), temporal)
    assert client.get("/api/v1/admin/triage/schedules", headers=_officer_headers()).status_code == 200
    assert (
        client.post(
            "/api/v1/admin/triage/trigger-batch",
            json={"cadence_type": "weekly", "include_unassigned_only": True},
            headers=_officer_headers(),
        ).status_code
        == 202
    )
    assert client.get("/api/v1/admin/triage/batch-jobs", headers=_officer_headers()).status_code == 200


def test_trigger_rejects_unknown_cadence(_clear_overrides):
    client = officer_client(ScriptedSession([]))
    response = client.post(
        "/api/v1/admin/triage/trigger-batch",
        json={"cadence_type": "monthly", "include_unassigned_only": True},
        headers=_officer_headers(),
    )
    assert response.status_code == 400


def test_trigger_starts_real_weekly_workflow(_clear_overrides):
    temporal = FakeTemporal()
    client = officer_client(ScriptedSession([]), temporal)
    response = client.post(
        "/api/v1/admin/triage/trigger-batch",
        json={"cadence_type": "weekly", "include_unassigned_only": True},
        headers=_officer_headers(),
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "STARTED" and body["batch_workflow_id"].startswith("batch-triage-")
    assert body["stream_url"].endswith(f"/stream") and "batch-jobs" in body["stream_url"]
    assert len(temporal.started) == 1
    call = temporal.started[0]
    assert call["workflow"] == "WeeklyBatchTriageWorkflow"
    assert call["task_queue"] == "triage-queue"
    assert call["args"][0] == body["batch_workflow_id"]


def test_schedules_get_defaults_and_put_roundtrip(_clear_overrides):
    temporal = FakeTemporal()
    client = officer_client(ScriptedSession([FakeResult([]), FakeResult([])]), temporal)
    response = client.get("/api/v1/admin/triage/schedules", headers=_officer_headers())
    assert response.status_code == 200, response.text
    assert response.json()["active_cadence"] == "weekly"

    client2 = officer_client(ScriptedSession([FakeResult([])]), temporal)
    response2 = client2.put(
        "/api/v1/admin/triage/schedules",
        json={"cron_expression": "0 2 * * 1", "monthly_macro_cron": "0 3 1 * *", "active_cadence": "weekly"},
        headers=_officer_headers(),
    )
    assert response2.status_code == 200, response2.text
    assert temporal.schedules_created == ["nitivayu-batch-weekly", "nitivayu-batch-monthly"]


def test_put_rejects_bad_cron(_clear_overrides):
    client = officer_client(ScriptedSession([]))
    response = client.put(
        "/api/v1/admin/triage/schedules",
        json={"cron_expression": "not a cron", "monthly_macro_cron": "0 3 1 * *", "active_cadence": "weekly"},
        headers=_officer_headers(),
    )
    assert response.status_code in (400, 422)


def test_history_lists_runs(_clear_overrides):
    run = BatchRun(batch_id="batch-triage-abc123", cadence="weekly", status="COMPLETED", total=3, processed=3)
    run.started_at = datetime.now(timezone.utc)
    run.finished_at = datetime.now(timezone.utc)
    client = officer_client(ScriptedSession([FakeResult([run])]))
    response = client.get("/api/v1/admin/triage/batch-jobs", headers=_officer_headers())
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1 and body[0]["batch_id"] == "batch-triage-abc123"


def test_stream_requires_officer(_clear_overrides):
    client = officer_client(ScriptedSession([]))
    response = client.get("/api/v1/admin/triage/batch-jobs/anything/stream")
    assert response.status_code == 403


def test_stream_unknown_batch_is_404(_clear_overrides):
    client = officer_client(ScriptedSession([]))
    response = client.get(
        "/api/v1/admin/triage/batch-jobs/nope/stream",
        params={"token": create_access_token({"sub": "o", "role": "officer"})},
    )
    assert response.status_code == 404


def test_models_and_worker_registration():
    import app.activities.cluster as cluster_mod
    import app.activities.extract as extract_mod
    import app.activities.notify as notify_mod
    import app.activities.report_gen as reports_mod
    import app.activities.route as route_mod
    from app.workflows.monthly_macro import MonthlyMacroTriageWorkflow
    from app.workflows.sla_workflow import UniversitySLAWorkflow
    from app.workflows.weekly_batch import WeeklyBatchTriageWorkflow

    assert CadenceConfig.__tablename__ == "cadence_configs"
    assert BatchRun.__tablename__ == "batch_runs"
    for workflow_cls in (WeeklyBatchTriageWorkflow, MonthlyMacroTriageWorkflow, UniversitySLAWorkflow):
        assert callable(getattr(workflow_cls, "run", None))
    for fn in (
        extract_mod.fetch_pending_batch_submissions_activity,
        extract_mod.batch_extract_and_embed_activity,
        cluster_mod.cluster_and_deduplicate_batch_activity,
        route_mod.global_university_routing_activity,
        reports_mod.generate_triage_csv_report_activity,
        reports_mod.generate_weekly_routing_pdf_report_activity,
        notify_mod.notify_officers_weekly_digest_activity,
        notify_mod.send_sla_warning_activity,
        notify_mod.escalate_to_state_admin_activity,
    ):
        assert hasattr(fn, "__temporal_activity_definition"), fn
