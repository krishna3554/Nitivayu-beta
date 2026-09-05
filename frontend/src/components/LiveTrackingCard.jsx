import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { getComplaint } from '../services/api';
import { SeverityBadge, StatusBadge, Timeline } from './ui';

const STAGE_OF = {
  INGESTED: 0, PENDING_TRIAGE: 1, TRIAGING: 1, PENDING_OFFICER_REVIEW: 2, OFFICER_REVIEW: 2,
  ROUTED: 3, ROUTED_TO_UNIVERSITY: 3, OFFERED: 3, ACCEPTED: 4, TEAM_FORMED: 4,
  SUBMITTED: 4, VERIFIED: 4, COMPLETED: 5, RESOLVED: 5, REJECTED: 5, MERGED: 5,
};
const STAGES = ['Submitted', 'AI triaging', 'Officer review', 'Routed', 'Under work', 'Resolved'];

/**
 * Public live tracker. Token-gated (no login). Polls today; upgrades to SSE
 * on the shared pub/sub backbone without changing this view (Phase 5).
 */
export default function LiveTrackingCard() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);

  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const res = await getComplaint(token);
        if (!live) return;
        setData(res.data); setError(''); setUpdatedAt(new Date());
      } catch (err) { if (live) setError(err.response?.data?.detail || 'We could not find this tracking token. Check it and try again.'); }
    };
    load();
    const t = setInterval(load, 30000);
    return () => { live = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const stageIdx = STAGE_OF[String(data?.status || '').toUpperCase()] ?? 0;
  const steps = STAGES.map((label, i) => ({
    label,
    state: i < stageIdx ? 'done' : i === stageIdx ? 'active' : 'pending',
    sub: i === 3 && data?.matched_university ? data.matched_university : undefined,
  }));

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-6">
      <p className="type-caption text-primary">Live tracker</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-mono text-2xl font-bold tracking-tight">{token}</h1>
        <p className="flex items-center gap-1.5 text-xs text-zinc-500">
          <RefreshCw className="h-3 w-3" />
          {updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : 'Loading…'} · auto-refreshes
        </p>
      </div>

      {error && !data && (
        <div className="card mt-6 border-rose-200 bg-rose-50 p-6 text-center">
          <p className="text-sm text-rose-700">{error}</p>
          <Link to="/track" className="btn-secondary mt-4 inline-block !py-2">Try another token</Link>
        </div>
      )}

      {data && (
        <>
          <div className="card mt-6 p-6">
            <div className="flex flex-wrap gap-2">
              <StatusBadge status={data.status} />
              {data.category && <span className="tag-chip !text-xs">{data.category}</span>}
              {data.severity != null && data.severity !== '' && <SeverityBadge value={data.severity} />}
              {data.district && <span className="tag-chip !text-xs">{data.district}</span>}
            </div>
            <h2 className="mt-4 text-xl font-medium-plus">{data.title || 'Your civic issue is being processed'}</h2>
            {data.summary && <p className="type-body-md mt-2 text-zinc-500">{data.summary}</p>}
          </div>

          <div className="card mt-4 p-6">
            <h2 className="type-label-sm text-zinc-500">Progress</h2>
            <div className="mt-4"><Timeline steps={steps} /></div>
          </div>

          {data.matched_university && (
            <div className="card mt-4 border-emerald-200 bg-emerald-50/50 p-6">
              <h2 className="type-label-sm text-emerald-800">Matched university</h2>
              <p className="mt-1 text-lg font-medium-plus text-emerald-900">{data.matched_university}</p>
              <p className="type-body-sm mt-1 text-emerald-700">Chosen for domain expertise, capacity, and proximity — verified by an officer.</p>
            </div>
          )}

          {(data.milestones?.length > 0) && (
            <div className="card mt-4 p-6">
              <h2 className="type-label-sm text-zinc-500">Milestones M1–M3</h2>
              <ol className="mt-3 space-y-2">
                {data.milestones.map((m, i) => (
                  <li key={m.milestone_id || i} className="flex items-center justify-between rounded-sm border border-border bg-surface-muted px-3 py-2 text-sm">
                    <span>M{m.milestone_num || i + 1}: {m.title}</span>
                    <StatusBadge status={m.status} />
                  </li>
                ))}
              </ol>
            </div>
          )}

          {(data.activity?.length > 0) && (
            <div className="card mt-4 p-6">
              <h2 className="type-label-sm text-zinc-500">Latest activity</h2>
              <ul className="mt-3 space-y-3">
                {data.activity.slice(0, 10).map((a, i) => (
                  <li key={a.log_id || i} className="flex gap-3 text-sm">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden />
                    <span>
                      <span className="font-medium-plus">{String(a.action || '').replace(/_/g, ' ')}</span>
                      <span className="ml-2 text-xs text-zinc-400">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
