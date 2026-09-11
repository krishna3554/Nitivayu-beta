import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Inbox } from 'lucide-react';
import OfficerReviewQueue from '../../components/OfficerReviewQueue';
import BatchTriageControl from '../../components/BatchTriageControl';
import { EmptyState, PageBack } from '../../components/ui';
import { getEscalations } from '../../services/api';

/** Officer queue tab — the Fireworks-styled review table. */
export function OfficerQueuePage() {
  return (
    <div>
      <h1 className="type-display-md !text-3xl">Review queue</h1>
      <p className="type-body-md mt-2 max-w-2xl text-zinc-500">AI structures every report; you approve, override, or reject. Nothing routes without your decision.</p>
      <div className="mt-5"><OfficerReviewQueue /></div>
    </div>
  );
}

export function OfficerBatchPage() {
  return (
    <div>
      <PageBack to="/app/officer" label="Back to Review queue" />
      <h1 className="type-display-md mt-3 !text-3xl">Batch control</h1>
      <p className="type-body-md mt-2 max-w-2xl text-zinc-500">Weekly clustering, capacity re-balancing, and official CSV/PDF exports. Real-time reports never wait for the batch.</p>
      <div className="mt-5"><BatchTriageControl /></div>
    </div>
  );
}

const REASON_LABEL = { ESCALATED: 'Escalated by triage', SEVERITY_CRITICAL: 'Severity 5 — critical', SLA_BREACH_RISK: 'SLA breach risk' };

/** Escalations — server-side list: SLA risk, severity-5, or workflow-escalated. */
export function OfficerEscalationsPage() {
  const [rows, setRows] = useState([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    getEscalations()
      .then(({ data }) => setRows(data?.items || []))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-4xl flex-col">
      <PageBack to="/app/officer" label="Back to Review queue" />
      <h1 className="type-display-md mt-3 !text-3xl">Escalations</h1>
      <p className="type-body-md mt-2 text-zinc-500">SLA breach risk, severity-5 reports, and workflow escalations — decide these first.</p>
      <div className="mt-5 flex flex-1 flex-col justify-center">
        {loading ? (
          <div className="space-y-3" aria-label="Loading escalations">
            {[0, 1, 2].map((i) => <div key={i} className="card h-20 animate-pulse" />)}
          </div>
        ) : failed ? (
          <EmptyState icon={Inbox} title="Could not load escalations — check your connection, then reopen this tab." actionLabel="Back to queue" actionTo="/app/officer" />
        ) : !rows.length ? (
          <EmptyState icon={Inbox} title="No escalations right now — every report in your district is inside its SLA window." actionLabel="Review the full queue" actionTo="/app/officer" />
        ) : (
          <ul className="space-y-3">
            {rows.map((r) => (
              <li key={r.id} className="card flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium-plus">{r.title || r.id}</p>
                  <p className="mt-1 font-mono text-xs text-zinc-500">
                    {r.id} · {r.district} · {REASON_LABEL[r.reason] || r.reason}
                    {r.age_hours != null ? ` · ${r.age_hours}h old` : ''}
                  </p>
                </div>
                <Link to={`/app/officer/review/${r.id}`} className="btn-secondary shrink-0 !py-2">Decide</Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
