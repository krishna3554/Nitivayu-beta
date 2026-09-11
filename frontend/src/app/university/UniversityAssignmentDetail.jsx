import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Inbox } from 'lucide-react';
import { MediaGallery, AudioPlayer, LocationBlock } from '../../components/CasefileBits';
import { PageBack, EmptyState, SeverityBadge, SLACountdown, StatusBadge, ScoreBreakdown } from '../../components/ui';
import { getAssignmentDetail, respondToAssignment } from '../../services/api';
import { useMetaConfig, milestoneLabel } from '../../lib/meta';

const LANG_NAMES = { hi: 'Hindi', en: 'English', hinglish: 'Hinglish', 'hi-Latn': 'Hinglish' };

/** Full university casefile: everything the officer saw + workspace specifics. */
export default function UniversityAssignmentDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { config } = useMetaConfig();

  const load = async () => {
    setLoading(true); setFailed(false);
    try {
      const { data: detail } = await getAssignmentDetail(id);
      setData(detail);
    } catch { setFailed(true); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [id]);

  const respond = async (response) => {
    setSaving(true);
    try { await respondToAssignment(id, { response }); await load(); }
    catch (err) { alert(err.response?.data?.detail || 'Unable to save your response.'); }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl" aria-label="Loading challenge">
        <div className="card h-10 w-48 animate-pulse" />
        <div className="card mt-4 h-64 animate-pulse" />
      </div>
    );
  }
  if (failed || !data) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageBack to="/app/university" label="Back to inbox" />
        <div className="mt-4"><EmptyState icon={Inbox} title="Could not load this challenge — it may have been rerouted." actionLabel="Back to inbox" actionTo="/app/university" /></div>
      </div>
    );
  }

  const problem = data.problem || {};
  const sub = data.submission || {};
  const photos = (data.media || []).filter((m) => m.kind === 'photo');
  const audio = (data.media || []).find((m) => m.kind === 'audio');
  const lang = LANG_NAMES[sub.language_pref] || (sub.language_pref ? sub.language_pref : 'Not recorded');
  const offered = data.status === 'OFFERED';

  return (
    <div className="mx-auto max-w-3xl">
      <PageBack to="/app/university" label="Back to inbox" />
      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <h1 className="type-display-md !text-3xl">{problem.title || 'Challenge'}</h1>
        <SLACountdown deadline={data.sla_deadline} totalHours={config.university_sla_hours} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <StatusBadge status={data.status} />
        {problem.category && <span className="tag-chip !text-xs">{problem.category}</span>}
        {problem.severity != null && <SeverityBadge value={problem.severity} />}
      </div>

      {/* Citizen report — full payload */}
      <section className="card mt-5 p-6" aria-label="Citizen report">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium-plus">Citizen report</h2>
          <span className="tag-chip !text-xs">Original · {lang}</span>
        </div>
        <p className="type-body-md mt-3 whitespace-pre-wrap text-ink">{sub.raw_text || problem.summary}</p>
        {photos.length > 0 && (
          <div className="mt-5">
            <h3 className="type-label-sm text-zinc-500">Photos ({photos.length})</h3>
            <div className="mt-2"><MediaGallery assets={data.media} /></div>
          </div>
        )}
        {audio && (
          <div className="mt-5">
            <h3 className="type-label-sm mb-2 text-zinc-500">Audio note</h3>
            <AudioPlayer asset={audio} />
          </div>
        )}
        <div className="mt-5">
          <h3 className="type-label-sm mb-2 text-zinc-500">Location</h3>
          <LocationBlock submission={sub} />
        </div>
        <p className="type-body-sm mt-4 text-zinc-500">
          Citizen tracking token (reference): {problem.tracking_token ? <span className="font-mono text-ink-secondary">{problem.tracking_token}</span> : '—'}
        </p>
      </section>

      {/* Workspace specifics */}
      <section className="card mt-4 p-6" aria-label="Assignment details">
        <h2 className="text-lg font-medium-plus">Your assignment</h2>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-zinc-500">Assigned department</dt><dd className="font-medium-plus">{data.assigned_department || '—'}</dd></div>
          <div><dt className="text-xs text-zinc-500">Acceptance deadline (7-day SLA)</dt><dd>{data.sla_deadline ? new Date(data.sla_deadline).toLocaleString() : '—'}</dd></div>
          <div><dt className="text-xs text-zinc-500">Match score</dt><dd className="font-mono text-primary">{Number(data.match_score).toFixed(3)}</dd></div>
          <div><dt className="text-xs text-zinc-500">Milestone structure</dt><dd>{(config.milestone_structure || []).map((m) => milestoneLabel(config, m.num)).join(' → ')}</dd></div>
        </dl>
        {data.score_breakdown && (
          <div className="mt-4 max-w-md">
            <p className="type-caption text-zinc-400">Why this match</p>
            <div className="mt-2"><ScoreBreakdown breakdown={data.score_breakdown} total={data.match_score} weights={config.score_weights} /></div>
          </div>
        )}
        {data.team && (
          <p className="type-body-sm mt-4 text-zinc-500">
            Team: {data.team.faculty_mentor_name} · Lead: {data.team.student_lead_name} · <Link to="/app/university/projects" className="link-inline !text-sm font-medium-plus">Open in Active projects</Link>
          </p>
        )}
        {offered && (
          <div className="mt-4 flex gap-2">
            <button onClick={() => respond('ACCEPT')} disabled={saving} className="btn-primary !py-2 disabled:opacity-60">Accept challenge</button>
            <button onClick={() => respond('DECLINE')} disabled={saving} className="btn-secondary !py-2 disabled:opacity-60">Decline</button>
          </div>
        )}
      </section>

      {/* Progress updates on this challenge */}
      {(data.updates || []).length > 0 && (
        <section className="card mt-4 p-6" aria-label="Progress updates">
          <h2 className="text-lg font-medium-plus">Progress updates ({data.updates.length})</h2>
          <ul className="mt-4 space-y-3">
            {data.updates.map((u) => (
              <li key={u.update_id} className="rounded-sm border border-border bg-surface-muted p-3 text-sm">
                <p>{u.note}</p>
                <p className="mt-1 text-xs text-zinc-500">{u.author_name || 'University team'} · {u.milestone} · {u.created_at ? new Date(u.created_at).toLocaleString() : ''}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
