import React, { useEffect, useState } from 'react';
import { Inbox, Users } from 'lucide-react';
import { EmptyState, PageBack, MilestoneBurst, SeverityBadge, SLACountdown, StatusBadge } from '../../components/ui';
import { getUniversityInbox, getUniversityProjects, getUniversityWorkspace, respondToAssignment } from '../../services/api';

export function UniversityInboxPage() {
  const [inbox, setInbox] = useState([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try { const { data } = await getUniversityInbox(); setInbox(Array.isArray(data) ? data : []); setFailed(false); }
    catch { setFailed(true); } finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const respond = async (id, response) => {
    try { await respondToAssignment(id, { response }); await refresh(); }
    catch (err) { alert(err.response?.data?.detail || 'Unable to save your response.'); }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="type-display-md !text-3xl">Challenge inbox</h1>
      <p className="type-body-md mt-2 text-zinc-500">Officer-verified challenges matched to your departments. Accept within 7 days — a warning arrives at 48 hours remaining.</p>
      <div className="mt-5">
        {loading ? <InboxSkeleton /> : failed ? (
          <EmptyState icon={Inbox} title="Could not load your inbox — check your connection, then retry." actionLabel="Retry" onAction={refresh} />
        ) : !inbox.length ? (
          <EmptyState icon={Inbox} title="No offered challenges right now — approved matches for your university will land here." actionLabel="View active projects" actionTo="/app/university/projects" />
        ) : (
          <ul className="space-y-4">
            {inbox.map((item) => (
              <li key={item.assignment_id} className="card p-5">
                <div className="flex flex-wrap gap-2">
                  <StatusBadge status={item.status} />
                  {item.severity != null && <SeverityBadge value={item.severity} />}
                  {item.category && <span className="tag-chip !text-xs">{item.category}</span>}
                  <span className="ml-auto"><SLACountdown deadline={item.sla_deadline} totalHours={168} /></span>
                </div>
                <h2 className="mt-3 text-lg font-medium-plus">{item.problem_title}</h2>
                {item.summary && <p className="type-body-sm mt-1 text-zinc-500">{item.summary}</p>}
                <div className="mt-4 flex items-center justify-between gap-4">
                  <p className="font-mono text-sm text-primary">match {Number(item.match_score).toFixed(3)}</p>
                  <span className="flex gap-2">
                    <button onClick={() => respond(item.assignment_id, 'ACCEPT')} className="btn-primary !py-2">Accept challenge</button>
                    <button onClick={() => respond(item.assignment_id, 'DECLINE')} className="btn-secondary !py-2">Decline</button>
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function UniversityProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    getUniversityProjects().then(({ data }) => setProjects(Array.isArray(data) ? data : [])).catch(() => setFailed(true));
  }, []);
  return (
    <div className="mx-auto max-w-3xl">
      <PageBack to="/app/university" label="Back to inbox" />
      <h1 className="type-display-md mt-3 !text-3xl">Active projects</h1>
      <p className="type-body-md mt-2 text-zinc-500">Teams, mentors, and M1–M3 evidence live here until field handover.</p>
      <div className="mt-5">
        {failed ? <EmptyState icon={Users} title="Could not load your projects — retry in a moment." actionLabel="Back to inbox" actionTo="/app/university" />
        : !projects.length ? <EmptyState icon={Users} title="No active projects yet — accept a challenge from your inbox to start your first team." actionLabel="Open inbox" actionTo="/app/university" />
        : (
          <ul className="space-y-4">
            {projects.map((p) => (
              <li key={p.team_id} className="card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-medium-plus">{p.title || p.problem_title || 'Project team'}</h2>
                    <p className="type-body-sm mt-1 text-zinc-500">{p.faculty_mentor_name && `Mentor: ${p.faculty_mentor_name} · `}{p.student_lead_name && `Lead: ${p.student_lead_name}`}</p>
                  </div>
                  <StatusBadge status={p.status} />
                </div>
                {(p.milestones || []).length > 0 && (
                  <ol className="mt-4 space-y-2">
                    {p.milestones.map((m) => {
                      const verified = String(m.status || '').toUpperCase() === 'VERIFIED';
                      return (
                      <li key={m.milestone_id || m.milestone_num} className={`flex items-center justify-between rounded-sm border border-border bg-surface-muted px-3 py-2 text-sm ${verified ? 'relative' : ''}`}>
                        {verified && <span aria-hidden className="glow-accent glow-loop" />}
                        {verified && <MilestoneBurst />}
                        <span className="relative z-10">M{m.milestone_num}: {m.title}</span>
                        <span className="relative z-10"><StatusBadge status={m.status} /></span>
                      </li>
                      );
                    })}
                  </ol>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function UniversityProfilePage() {
  const [ws, setWs] = useState(null);
  useEffect(() => { getUniversityWorkspace().then(({ data }) => setWs(data)).catch(() => {}); }, []);
  return (
    <div className="mx-auto max-w-xl">
      <PageBack to="/app/university" label="Back to inbox" />
      <h1 className="type-display-md mt-3 !text-3xl">IIC profile</h1>
      <div className="card mt-5 space-y-3 p-6">
        <Row k="Institution" v={ws?.name || 'Your university'} />
        <Row k="Code" v={ws?.short_code || '—'} />
        <Row k="District" v={ws?.district || '—'} />
        <Row k="Specializations" v={(ws?.domain_specializations || []).join(', ') || '—'} />
        <Row k="Capacity" v={ws ? `${ws.current_load ?? 0} / ${ws.active_capacity ?? '—'} active` : '—'} />
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between gap-6 border-b border-border pb-3 last:border-0 last:pb-0">
      <dt className="type-label-sm shrink-0 text-zinc-500">{k}</dt>
      <dd className="text-right text-sm">{v}</dd>
    </div>
  );
}

function InboxSkeleton() {
  return (
    <div className="space-y-4" aria-label="Loading inbox">
      {[0, 1].map((i) => <div key={i} className="card h-44 animate-pulse" />)}
    </div>
  );
}
