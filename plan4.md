# Plan 4 — Complete Working Backend Pipeline

**Goal:** replace every hardcoded/mock UI surface with real backend data and finish the
half-wired backend pipeline (workflows that never run, tables that are never written,
endpoints the UI never calls), so the whole product works end-to-end on live data.

**Stack (as-is, no changes):** FastAPI + async SQLAlchemy + Postgres 16/pgvector +
Temporal + Redis + MinIO. React/Vite frontend behind nginx at `/api/v1`.

## 0. Implementation status — updated 2026-09-08 (post-re-audit)

**99 pytest tests green; `npm run build` clean; full loop runs live in Docker.**

Status changes since the original plan (verified against code and live containers):
- **WP-0** ✅ done — orphaned route files + legacy components deleted; LLM cache is
  Redis-backed (`llm:cache:<sha256>`, 7 d TTL); `.env` untracked (`git rm --cached`).
- **WP-1** ✅ done — `submissions.user_id` live; `/citizen/reports` + `/reports/claim`;
  `/auth/me` GET/PATCH; CitizenProfile bound to real data.
- **WP-2** ✅ done — `/meta/config`, `/meta/demo-accounts` (404 unless `DEMO_MODE=true`),
  `/meta/public-stats`, `/meta/partners`, `/meta/featured-cases`; UI constants consume them.
- **WP-3** ✅ done — `/officer/escalations`; `assigned_officer_id` written on decision;
  queue returns `{items, total, has_more}`; audit rows carry ip/request-id.
- **WP-4** ✅ done — officer APPROVE/OVERRIDE starts `UniversitySLAWorkflow`;
  respond sends accept/decline signal; ACCEPT auto-creates ProjectTeam + M1/M2/M3 and
  bumps `universities.current_load` (decrement on DECLINE/ESCALATED/COMPLETED).
- **WP-5** ✅ done — milestone submit/verify endpoints + UI; M3 verify completes the
  problem and decrements load; casefile + tracker expose milestone state.
- **WP-6** ✅ done — `routes/admin_exports.py`: invites list wired, 4 exports +
  auth-gated download, `/admin/health/services` powers the dashboard badges.
- **WP-7** ✅ done — `/industry/impact` + `/industry/exports/monthly-matrix`; the
  fabricated funding-goal progress bars were deleted instead of adding a fake column.
- **WP-8** ✅ done — landing/impact pages consume the public meta endpoints; no fabricated
  case-study scores remain (empty-state when no completed cases).
- **WP-9** ✅ done (adapted) — `services/notify.py` (identity OTP + admin invites) and
  `services/notify_reporter.py` (reporter updates) with **live Gmail SMTP** and **live
  Twilio SMS** (both verified by real delivery). Reporter contact comes from per-report
  opt-in (`submissions.contact_email/contact_phone/notify_consent`) instead of the
  deferred `PHONE_FERNET_KEY` design — plaintext contact is opt-in only, documented.
  `ALLOW_DEV_OTP=true` remains on for the demo; **set false for any real deployment**.
- **WP-12** ✅ done — tracker is SSE-first with polling fallback; officer queue +
  university inbox toast on `role:`/`org:` channels.
- **WP-13** ✅ done (adapted) — kept `init_db.sql` + numbered idempotent migrations;
  new identity/batch/contact columns synced into both (`init_db.sql` + live ALTERs).

New work landed beyond the original plan (now stable):
- **Google OAuth** hardened (signed state + TTL, id_token aud/iss/exp verify,
  one-time `?code=` exchange, workspace-linkable emails); Facebook retired.
- **Batch triage for real:** `/admin/triage` trigger/schedules/history/SSE wired to the
  actual `WeeklyBatchTriageWorkflow` (fetch → extract+embed → cluster/dedup →
  capacity-balanced route → `Nitivayu_*` CSV + routing PDF → officer digest), with
  `cadence_configs` + `batch_runs` tables and a live Temporal weekly schedule.
- **DB engine is lazy** (no import-time crashes), login is fail-closed (bcrypt enforced;
  email-substring role guessing removed), uploads bypass the axios JSON-transform bug,
  and nginx serves fresh HTML with immutable hashed assets.

Remaining gaps are all in §1.2/§1.3 below — the table is the source of truth.

## 1. Remaining gaps (verified against the code, 2026-09-08)

### 1.1 Backend — only two real gaps left

| # | Gap | Evidence | Severity |
|---|---|---|---|
| B2 | ✅ fixed 2026-09-08 — monthly workflow repaired (typed activity refs + payloads); all 4 macro activities real (`activities/macro.py`); monthly Temporal schedule created from `monthly_macro_cron` (`nitivayu-batch-monthly`, next run 2026-10-01); verified by live manual run (8 centroids, 19 CSR suggestions, overrides JSON, XLSX); re-PUT idempotent | `workflows/monthly_macro.py`, `activities/macro.py`, `routes/batch_triage.py` | done |
| B10 | Media pipeline: `MediaProcessingWorkflow` starts on upload, but `scan`/`normalize` are pass-through and `transcribe_audio_activity` always returns `{transcript: None}` (ASR_ENABLED=false by design); no EXIF strip | `activities/media.py` | partial (honest stubs) |

Small integrity leftovers (no crashes, code paths to write):
`audit_logs.ip_address/request_id` are written by new code but old rows are NULL;
`citizens` table is seed-only by design; `problems.funding_goal_inr` deliberately dropped.

### 1.2 Frontend — thin remainder

| # | UI surface | State |
|---|---|---|
| F6 | Officer escalations page | endpoint consumed; visual polish only (grouping, SLA bar) |
| F14 | Tracker SSE | working with polling fallback; add reconnect/backoff jitter |
| F15 | Legacy components | deleted |
| F17 | Queue virtualization | copy fixed; **real** pagination/virtualization only needed past ~200 rows |

### 1.3 Ops/scale (non-blocking for demo)

- Worker image is 10 GB (torch/CUDA) — slim it (CPU torch wheel, no nvidia stack) before
  any hosted deploy; build takes ~10 min today.
- MinIO is healthy but **not started in compose** when another project holds `:9000` —
  storage currently uses the local mirror. Resolve the port ownership before enabling S3.
- Root `.env` holds live Twilio + Google + SMTP creds (untracked — good). Rotate the
  Twilio token (was pasted in chat) and the OpenRouter key (in old git history).

## 2. Suggested remaining order

| Order | Item | Effort | Why |
|---|---|---|---|
| 1 | Secret rotation (OpenRouter, Twilio, Google) | 0.25 d | burned secrets |
| 2 | B10 media: Pillow EXIF strip + magic-byte scan; optional faster-whisper behind `ASR_ENABLED` | 1.5 d | heaviest remaining worker work |
| 4 | Worker image slimming + MinIO port resolution | 0.5 d | deploy hygiene |
| 5 | Frontend polish: escalations view, SSE backoff, queue pagination >200 rows | 0.5 d | scale polish |
| 6 | Load-test proof (120 RPS / 10k-row queue) + K8s manifests | 1 d | §5.x spec closure |

**Definition of done stands:** endpoint tests per item, no localStorage/hardcoded source
for covered UI, and the full loop runs: submit → triage → officer approve → university
accept → milestones → verify → completed → CSR pledge → exports.
