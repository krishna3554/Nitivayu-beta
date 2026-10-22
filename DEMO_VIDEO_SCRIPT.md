# Nitivayu — 5-Minute Demo Video Script

## Recording setup

- Open `http://localhost:3000`.
- Keep the browser at 1280×720 or larger.
- Record the browser window with microphone narration.
- Use the demo accounts shown by the app’s login screen or `GET /meta/demo-accounts` when demo mode is enabled.

## Timeline and narration

### 0:00–0:25 — Opening

“This is Nitivayu, a civic-intelligence platform that turns citizen grievances into research-ready challenges, routes them to accountable officers and universities, and tracks progress through completion.”

Show the landing page, navigation, language options, and the main call to action.

### 0:25–1:05 — Citizen report intake

Open the citizen reporting flow. Show the multilingual title/description fields, category, severity, location, optional contact consent, photo/audio evidence, and submit action.

Narrate: “Citizens can submit a problem in Hindi, Hinglish, or English, add location and evidence, and choose whether they want updates. The platform validates the input and protects personal information.”

Submit a demo report and show the confirmation/tracking identifier.

### 1:05–1:45 — Triage and explainable routing

Switch to the officer workspace. Show the incoming report, extracted summary, category, severity, location hint, duplicate suggestions, and routing recommendation.

Narrate: “Temporal workflows process the report durably: extract, classify, embed, deduplicate, and route. Officers see an explainable match score instead of a black-box decision.”

Open the score breakdown and briefly show the officer approve, override, reject, or escalate controls.

### 1:45–2:25 — SLA and accountability

Show the officer queue, SLA timers, escalation feed, and audit history.

Narrate: “The officer review has a 72-hour SLA. Missed deadlines escalate automatically, and every important action is recorded in an immutable audit trail.”

Show the audit entry and the live status transition.

### 2:25–3:10 — University assignment and milestones

Switch to the university workspace. Show an accepted challenge, assignment details, team members, and milestone cards M1, M2, and M3.

Narrate: “Once approved, the challenge can be accepted by a university. Teams receive milestones, submit updates and evidence, and move the case toward verified completion.”

Open a milestone update form, submit a demo update, and show the updated progress state.

### 3:10–3:45 — Industry and CSR funding

Switch to the industry workspace. Show opportunities, filters, pledge form, portfolio, and impact view.

Narrate: “Industry partners can discover validated challenges, pledge funding in INR, and monitor the resulting impact. Funding is linked to real projects rather than disconnected donations.”

Open the monthly funding-matrix export if available.

### 3:45–4:25 — Citizen tracking and reports feed

Return to the public/citizen view. Open tracking or My Reports, then the Reports Feed.

Narrate: “Citizens can follow their own reports and see public, privacy-safe progress. The reports feed exposes cleaned evidence and supports account-bound confirmations without exposing raw personal information.”

Show a report detail page, status timeline, and a confirmation/me-too action.

### 4:25–4:50 — Analytics, exports, and service health

Open the admin or telemetry workspace. Show overview metrics, category/district distributions, service health, and export controls.

Narrate: “Administrators get live operational telemetry, analytics, compliance exports, and service-health checks. The stack also exposes Prometheus and Grafana monitoring for operations.”

### 4:50–5:00 — Closing

“Nitivayu connects citizen voice, accountable review, university research, and CSR support in one durable workflow. Every report is traceable from intake to measurable impact.”

End on the dashboard or landing page with the project name visible.

## Suggested recording notes

- Use one seeded demo report so the same case can be followed across citizen, officer, university, and industry views.
- Keep each page on screen for 5–8 seconds before clicking.
- Hide browser bookmarks and personal notifications.
- If a workspace is unavailable, narrate the feature from the dashboard and continue; the main story is the report lifecycle.
