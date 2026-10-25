# Nitivayu Complete End-to-End Demonstration Script

This script is designed for a 12–15 minute live demonstration or a detailed recorded walkthrough. It follows one civic issue from citizen submission through AI triage, officer review, university execution, CSR funding, public tracking, and administration.

## 1. Demo preparation

### Start the platform

From the project root:

```bash
docker compose up -d
docker compose ps
```

Expected result: the 10 services are running, including PostgreSQL, Temporal, backend, worker, frontend, Redis, object storage, PgBouncer, Prometheus, and Grafana.

Open:

- Application: http://localhost:3000
- API documentation: http://localhost:8000/docs
- Temporal UI: http://localhost:8233
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

If the database is empty, seed the deterministic demo data:

```bash
docker compose exec backend python -m scripts.seed_data
```

### Demo accounts

| Workspace | Email | Password |
|---|---|---|
| Officer | `officer@nitivayu.gov.in` | `password123` |
| Senior officer | `sunita.devi@jharkhand.gov.in` | `password123` |
| Admin | `admin@nitivayu.in` | `admin` |
| University | `iic.head@bitmesra.ac.in` | any password |
| University | `iic.coord@nitjsr.ac.in` | any password |
| CSR industry | `csr@tatasteel.com` | any password |

The university and CSR demo accounts are contact-email demo logins. Use the exact email address.

## 2. Opening and product story — 0:00–1:00

### On screen

Open `http://localhost:3000` and show the landing page, navigation, role entry points, and headline metrics.

### Narration

“Nitivayu converts civic grievances into structured, research-ready challenges. A citizen submits a local issue, AI extracts the important facts, an officer makes the accountable decision, a university team works on the solution, and CSR partners can fund measurable progress. Every stage is durable, auditable, and visible to the right people.”

Point out the public navigation: Report, Track, Reports Feed, How it works, Impact, and role-specific login.

## 3. Citizen intake — 1:00–2:30

### On screen

1. Select **Report a problem**.
2. Enter a realistic issue:

   - Title: `Overflowing drains near the school in Ranchi`
   - Description: `During every heavy rain, the drain beside the school overflows. Children walk through dirty water and the road becomes unsafe.`
   - Category: `Sanitation` or `Infrastructure`
   - Severity: `4`
   - District: `Ranchi`
   - Add a harmless sample image if available.
   - Enable contact consent only if demonstrating notifications.

3. Submit the report.
4. Capture the tracking token shown in the confirmation.

### Narration

“The citizen can write in Hindi, Hinglish, or English, add location and evidence, and choose whether to receive updates. The intake collects enough context for triage without exposing unnecessary personal information.”

### Expected result

The application shows a success state and a public tracking link. Keep the token visible; it will be used later.

### API fallback

If the UI form is unavailable, use Swagger at `/docs` or submit through the project’s API client. Do not use real personal data in a demo.

## 4. Public Reports Feed — 2:30–3:15

### On screen

1. Open `/feed`.
2. Show newest-first reports.
3. Filter by district, category, and lifecycle status.
4. Open a report card and its clean evidence.
5. Copy the public tracker link.

### Narration

“The Reports Feed is public but privacy-safe. It exposes only reports that passed extraction, removes raw intake states, anonymizes the reporter, hides exact GPS and contacts, and displays only clean moderated media.”

If logged in as a citizen, demonstrate one **Me too** action, one **Confirm firsthand** action, and a moderated comment. Explain that each account can contribute only once per signal.

## 5. Officer login and AI triage — 3:15–5:00

### On screen

1. Log out if necessary.
2. Sign in with:

   - Email: `officer@nitivayu.gov.in`
   - Password: `password123`

3. Open the officer review queue.
4. Select a pending challenge.
5. Show the extracted title, summary, category, severity, district, evidence, duplicate suggestions, and university matches.

### Narration

“The backend starts a durable Temporal workflow. The pipeline extracts a structured summary, classifies the issue, creates an embedding, checks for duplicates, and ranks candidate universities.”

Show the explainable score breakdown:

- Theme match
- Semantic similarity
- University capacity
- Geographic fit

“The recommendation is explainable. Officers can see why a university was selected and remain responsible for the final decision.”

## 6. Officer decision and SLA — 5:00–6:30

### On screen

1. Approve the challenge.
2. Show the assignment changing to `ROUTED` or `OFFERED`.
3. Open the officer SLA or escalation view.
4. Show audit history and the decision record.

### Narration

“Approval routes the challenge to the selected university and starts the university SLA workflow. Officer review has a 72-hour SLA. If the deadline is missed, the workflow escalates and the event is audit logged.”

Also mention the other available decisions:

- **Reject** closes the challenge as rejected.
- **Override** lets the officer select a different university.
- **Escalate** makes the issue visible to senior administration.

## 7. University acceptance — 6:30–8:00

### On screen

1. Open a private/incognito browser window or log out.
2. Log in with:

   - Email: `iic.head@bitmesra.ac.in`
   - Password: `demo1234`

3. Open **Challenge inbox**.
4. Open the newly offered challenge.
5. Review evidence, casefile, score breakdown, and SLA deadline.
6. Click **Accept**.

### Narration

“The university sees only its own organization-scoped inbox. Accepting creates a project team and automatically creates milestones M1, M2, and M3. Declining or timing out releases the offer and allows the workflow to reroute to the next-ranked university.”

## 8. University project and milestones — 8:00–9:30

### On screen

1. Open **Active projects**.
2. Open the accepted project.
3. Fill or show the team details:

   - Faculty mentor: `Dr. P. Sharma`
   - Student lead: `Anjali Kumari`
   - Proposal: `Low-cost drainage monitoring and school safety plan`

4. Open M1, submit a short progress update, and attach a harmless evidence URL or note.
5. Show M1 moving to `SUBMITTED`.

### Narration

“The university workspace turns the routed challenge into an accountable project. Teams can provide mentor and student details, submit milestone evidence, and publish plain-language progress updates that later appear on the citizen tracker.”

Explain the lifecycle:

`PENDING → SUBMITTED → VERIFIED`

M3 verification completes the challenge and releases the university’s active capacity.

## 9. Officer milestone verification — 9:30–10:15

### On screen

1. Return to the officer workspace.
2. Open the submitted milestone.
3. Review the evidence.
4. Click **Verify**.

### Narration

“Verification is a second human accountability gate. The officer can verify or reject submitted evidence. Every change records the actor, timestamp, previous value, and new value.”

## 10. CSR funding — 10:15–11:15

### On screen

1. Log in as:

   - Email: `csr@tatasteel.com`
   - Password: `demo1234`

2. Open **Opportunities**.
3. Filter by category or district.
4. Open a routed or accepted challenge.
5. Submit a pledge, for example `1500000` INR.
6. Open **Portfolio** or **Impact**.

### Narration

“CSR partners discover validated challenges rather than isolated donation requests. They can pledge funding in INR, associate it with a project team, and see aggregated impact and funding totals.”

Show the monthly matrix export if enabled. Explain that it maps problem categories to CSR focus areas and produces an XLSX compliance artifact.

## 11. Citizen tracking — 11:15–12:15

### On screen

1. Open `/track`.
2. Paste the tracking token from the citizen submission.
3. Show the timeline:

   `Ingested → AI Triaging → Officer Review → Routed → Milestone R&D → Resolved`

4. Show university assignment, milestone progress, latest project update, and officer verification strip.

### Narration

“The citizen does not need an internal account to follow progress. The public tracker is token-based, uses server-sent events with polling fallback, and translates internal workflow activity into understandable progress updates.”

## 12. Admin, analytics, and operational health — 12:15–13:30

### On screen

1. Log in as `admin@nitivayu.in` / `admin`.
2. Open telemetry/dashboard.
3. Show:

   - Total submissions and problems
   - Triage throughput
   - SLA compliance
   - Category, district, and severity distributions
   - Active universities and pledged INR
   - Service-health badges

4. Open exports and show triage, SLA, audit, reports, and CSR output areas.
5. Optionally open Grafana and Temporal UI in separate tabs.

### Narration

“Administrators get one operational view across data, workflow, services, and compliance. Prometheus scrapes backend metrics, Grafana visualizes them, and Temporal exposes the durable workflow executions.”

## 13. Closing summary — 13:30–14:00

### Narration

“Nitivayu connects citizen voice, explainable AI, officer accountability, university research, and CSR support in one end-to-end workflow. The result is not just a ticketing system: it is a traceable path from a local problem to a verified, funded, and measurable solution.”

End on the landing page or the completed tracker.

## 14. Useful verification commands

```bash
# Service state
docker compose ps

# Backend health
curl http://localhost:8000/api/health

# Frontend response
curl -I http://localhost:3000/

# Demo account metadata (only when DEMO_MODE=true)
curl http://localhost:8000/api/v1/meta/demo-accounts

# Follow backend events while recording
docker compose logs -f backend worker
```

## 15. Recording checklist

- Use a clean browser profile with no personal notifications.
- Keep the browser window at 1280×720 or larger.
- Use one seeded report or one newly created report consistently.
- Never enter real phone numbers, email addresses, GPS coordinates, or private evidence.
- Pause briefly after every status transition so viewers can read it.
- Keep the tracking token in a text note for quick reuse.
- If a workflow step is slow, show Temporal UI or the backend logs while narrating what is happening.
- At the end, show the final tracker state and the project name.
