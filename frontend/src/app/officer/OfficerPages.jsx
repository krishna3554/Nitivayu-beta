import React, { useEffect, useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import OfficerReviewQueue from '../../components/OfficerReviewQueue';
import BatchTriageControl from '../../components/BatchTriageControl';
import { EmptyState, PageBack } from '../../components/ui';
import { getQueue } from '../../services/api';

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

/** Escalations — queue items past the 20% SLA warning threshold. */
export function OfficerEscalationsPage() {
  const [rows, setRows] = useState([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    getQueue({ limit: 100 })
      .then(({ data }) => setRows(Array.isArray(data) ? data : []))
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);
  const hot = useMemo(
    () => rows.filter((r) => Number(r.sla_hours_remaining) <= 72 * 0.2 || Number(r.severity) >= 5),
    [rows],
  );
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-4xl flex-col">
      <PageBack to="/app/officer" label="Back to Review queue" />
      <h1 className="type-display-md mt-3 !text-3xl">Escalations</h1>
      <p className="type-body-md mt-2 text-zinc-500">Reports under 20% SLA remaining — or severity 5 — decide these first.</p>
      <div className="mt-5 flex flex-1 flex-col justify-center">
        {loading ? (
          <div className="space-y-3" aria-label="Loading escalations">
            {[0, 1, 2].map((i) => <div key={i} className="card h-20 animate-pulse" />)}
          </div>
        ) : failed ? (
          <EmptyState icon={Inbox} title="Could not load escalations — check your connection, then reopen this tab." actionLabel="Back to queue" actionTo="/app/officer" />
        ) : !hot.length ? (
          <EmptyState icon={Inbox} title="No escalations right now — every report in your district is inside its SLA window." actionLabel="Review the full queue" actionTo="/app/officer" />
        ) : (
          <ul className="space-y-3">
            {hot.map((r) => (
              <li key={r.id} className="card flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium-plus">{r.title || r.id}</p>
                  <p className="mt-1 font-mono text-xs text-zinc-500">{r.id} · {r.district} · {r.sla_hours_remaining}h left</p>
                </div>
                <a href="/app/officer" className="btn-secondary shrink-0 !py-2">Decide</a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
