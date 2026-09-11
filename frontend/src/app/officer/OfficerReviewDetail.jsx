import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Check, X, Inbox, History, ShieldCheck } from 'lucide-react';
import { MediaGallery, AudioPlayer, LocationBlock } from '../../components/CasefileBits';
import { PageBack, StatusBadge, SeverityBadge, SLACountdown, ScoreBreakdown, EmptyState } from '../../components/ui';
import { getProblemDetail, getProblemUpdates, getOfficerUniversities, decideComplaint, verifyMilestone, clearFlaggedMedia } from '../../services/api';
import { useMetaConfig } from '../../lib/meta';

const LANG_NAMES = { hi: 'Hindi', en: 'English', hinglish: 'Hinglish', 'hi-Latn': 'Hinglish' };

export default function OfficerReviewDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [updates, setUpdates] = useState([]);
  const [universities, setUniversities] = useState([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrideTo, setOverrideTo] = useState('');
  const [comments, setComments] = useState('');

  const load = async () => {
    setLoading(true); setFailed(false);
    try {
      const [{ data: detail }, { data: ups }, { data: unis }] = await Promise.all([
        getProblemDetail(id),
        getProblemUpdates(id).catch(() => ({ data: [] })),
        getOfficerUniversities().catch(() => ({ data: [] })),
      ]);
      setData(detail);
      setUpdates(Array.isArray(ups) ? ups : []);
      setUniversities(Array.isArray(unis) ? unis : []);
    } catch { setFailed(true); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [id]);

  const { config } = useMetaConfig();

  const decide = async (payload) => {
    setSaving(true);
    try {
      await decideComplaint(id, payload);
      await load();
    } catch (err) { alert(err.response?.data?.detail || 'Unable to save your decision.'); }
    finally { setSaving(false); }
  };

  const verify = async (milestoneId, decision) => {
    const ok = decision === 'VERIFY' ? true : window.confirm('Send this milestone back for rework?');
    if (!ok) return;
    setSaving(true);
    try {
      await verifyMilestone(milestoneId, { decision, comments: comments || undefined });
      await load();
    } catch (err) { alert(err.response?.data?.detail || 'Unable to record verification.'); }
    finally { setSaving(false); }
  };

  const clearFlag = async (assetId) => {
    setSaving(true);
    try {
      await clearFlaggedMedia(assetId);
      await load();
    } catch (err) { alert(err.response?.data?.detail || 'Unable to clear this evidence.'); }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl" aria-label="Loading report">
        <div className="card h-10 w-48 animate-pulse" />
        <div className="card mt-4 h-64 animate-pulse" />
        <div className="card mt-4 h-48 animate-pulse" />
      </div>
    );
  }
  if (failed || !data) {
    return (
      <div className="mx-auto max-w-2xl">
        <PageBack to="/app/officer" label="Back to Review queue" />
        <div className="mt-4"><EmptyState icon={Inbox} title="Could not load this report — it may have been merged or removed." actionLabel="Back to queue" actionTo="/app/officer" /></div>
      </div>
    );
  }

  const sub = data.submission || {};
  const photos = (data.media || []).filter((m) => m.kind === 'photo');
  const audio = (data.media || []).find((m) => m.kind === 'audio');
  const flagged = (data.media || []).filter((m) => m.moderation_status === 'flagged');
  const top = (data.assignments || [])[0];
  const decided = data.status !== 'PENDING_OFFICER_REVIEW';
  const lang = LANG_NAMES[sub.language_pref] || (sub.language_pref ? sub.language_pref : 'Not recorded');
  const submittedMilestones = (data.milestones || []).filter((m) => m.status === 'SUBMITTED');

  return (
    <div className="mx-auto max-w-4xl">
      <PageBack to="/app/officer" label="Back to Review queue" />

      {/* Header */}
      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="type-display-md !text-3xl">{data.title}</h1>
          <p className="mt-1 font-mono text-xs text-zinc-400">{data.problem_id} · {sub.tracking_token}</p>
        </div>
        <SLACountdown slaHoursRemaining={data.sla_hours_remaining} totalHours={config.officer_sla_hours} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <StatusBadge status={data.status} />
        {data.category && <span className="tag-chip !text-xs">{data.category}</span>}
        {data.severity != null && <SeverityBadge value={data.severity} />}
      </div>

      {/* Citizen submission */}
      <section className="card mt-5 p-6" aria-label="Citizen submission">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium-plus">Citizen report</h2>
          <span className="tag-chip !text-xs">Original · {lang}</span>
        </div>
        <p className="type-body-md mt-3 whitespace-pre-wrap text-ink">{sub.raw_text || data.summary}</p>
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
        <dl className="mt-5 grid grid-cols-2 gap-2 border-t border-border pt-4 text-sm sm:grid-cols-4">
          <div><dt className="text-xs text-zinc-500">Reported by</dt><dd className="font-medium-plus">{sub.reporter_name || 'Anonymous'}</dd></div>
          <div><dt className="text-xs text-zinc-500">Tracking token</dt><dd className="font-mono text-xs">{sub.tracking_token || '—'}</dd></div>
          <div><dt className="text-xs text-zinc-500">Submitted</dt><dd>{sub.submitted_at ? new Date(sub.submitted_at).toLocaleString() : '—'}</dd></div>
          <div><dt className="text-xs text-zinc-500">Language</dt><dd>{lang}</dd></div>
          <div><dt className="text-xs text-zinc-500">AI confidence</dt><dd>{data.confidence != null ? `${Math.round(data.confidence * 100)}%` : '—'}</dd></div>
        </dl>
      </section>

      {/* AI match */}
      <section className="card mt-4 p-6" aria-label="University matches">
        <h2 className="text-lg font-medium-plus">Proposed matches</h2>
        {(data.assignments || []).length === 0 && <p className="type-body-sm mt-2 text-zinc-500">No university scored yet.</p>}
        <ol className="mt-4 space-y-4">
          {(data.assignments || []).map((a, i) => (
            <li key={a.assignment_id} className="rounded-sm border border-border bg-surface-muted p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium-plus">#{a.rank_order} {a.university_name || 'Awaiting match'}</p>
                <span className="font-mono text-sm text-primary">{Number(a.match_score).toFixed(3)}</span>
              </div>
              {a.score_breakdown && <div className="mt-2 max-w-md"><ScoreBreakdown breakdown={a.score_breakdown} total={a.match_score} weights={config.score_weights} /></div>}
              <p className="mt-2 text-xs text-zinc-500">Offer {a.status} {i === 0 && top ? `· SLA ${data.sla_hours_remaining ?? '—'}h left` : ''}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Decision */}
      <section className="card mt-4 p-6" aria-label="Your decision">
        <h2 className="text-lg font-medium-plus">Your decision</h2>
        {decided ? (
          <div className="mt-3 flex items-center justify-between gap-3">
            <StatusBadge status={data.status} />
            <Link to="/app/officer" className="btn-secondary !py-2">Back to queue</Link>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap gap-2">
              <button onClick={() => decide({ decision: 'APPROVE', comments: comments || undefined })} disabled={saving} className="btn-primary inline-flex items-center gap-2 disabled:opacity-60">
                <Check className="h-4 w-4" /> {saving ? 'Saving…' : 'Approve & route'}
              </button>
              <button onClick={() => { if (window.confirm('Reject this report?')) decide({ decision: 'REJECT', comments: comments || undefined }); }} disabled={saving} className="btn-secondary inline-flex items-center gap-2 !border-rose-200 !text-rose-700 disabled:opacity-60">
                <X className="h-4 w-4" /> Reject
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
              <label className="type-label-sm">Override university
                <select value={overrideTo} onChange={(e) => setOverrideTo(e.target.value)} className="input mt-1.5">
                  <option value="">Top match ({top?.university_name || 'none'})</option>
                  {universities.map((u) => <option key={u.university_id} value={u.university_id}>{u.name} · {u.district}</option>)}
                </select>
              </label>
              <button onClick={() => decide({ decision: 'OVERRIDE', override_university_id: overrideTo || undefined, comments: comments || undefined })} disabled={saving || !overrideTo} className="btn-secondary !py-2.5 disabled:opacity-50">Route to selected</button>
            </div>
            <label className="type-label-sm block">Verification comments <span className="text-zinc-400">(optional)</span>
              <input value={comments} onChange={(e) => setComments(e.target.value)} placeholder="e.g. Verified with district PHED" className="input mt-1.5" />
            </label>
          </div>
        )}
      </section>

      {/* Flagged evidence awaiting review */}
      {flagged.length > 0 && (
        <section className="card mt-4 border-amber-200 bg-amber-50/50 p-6" aria-label="Flagged evidence">
          <h2 className="flex items-center gap-2 text-lg font-medium-plus"><ShieldCheck className="h-4 w-4" /> Flagged evidence ({flagged.length})</h2>
          <p className="type-body-sm mt-1 text-zinc-500">Failed automated validation. Review, then clear to release to the university — or leave flagged to keep it hidden.</p>
          <ul className="mt-3 space-y-2">
            {flagged.map((m) => (
              <li key={m.asset_id} className="flex items-center justify-between gap-3 rounded-sm border border-amber-200 bg-white px-3 py-2 text-sm">
                <span className="font-mono text-xs">{m.kind} · {m.asset_id.slice(0, 8)}</span>
                <button onClick={() => clearFlag(m.asset_id)} disabled={saving} className="btn-secondary !py-1.5 disabled:opacity-60">Clear flag</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Milestone verification */}
      {(data.milestones || []).length > 0 && (
        <section className="card mt-4 p-6" aria-label="Milestone verification">
          <h2 className="text-lg font-medium-plus">Milestones M1–M3</h2>
          {submittedMilestones.length === 0 && <p className="type-body-sm mt-2 text-zinc-500">No milestones awaiting verification right now.</p>}
          <ol className="mt-4 space-y-3">
            {(data.milestones || []).map((m) => (
              <li key={m.milestone_id} className="rounded-sm border border-border bg-surface-muted p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium-plus">M{m.milestone_num}: {m.title}</p>
                  <StatusBadge status={m.status} />
                </div>
                {m.status === 'SUBMITTED' && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => verify(m.milestone_id, 'VERIFY')} disabled={saving} className="btn-primary inline-flex items-center gap-2 !py-2 disabled:opacity-60">
                      <Check className="h-4 w-4" /> Verify{m.milestone_num === 3 ? ' & close issue' : ''}
                    </button>
                    <button onClick={() => verify(m.milestone_id, 'REJECT')} disabled={saving} className="btn-secondary !py-2 disabled:opacity-60">Request rework</button>
                  </div>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Progress updates (officer audit view) */}
      {updates.length > 0 && (
        <section className="card mt-4 p-6" aria-label="University progress updates">
          <h2 className="flex items-center gap-2 text-lg font-medium-plus"><History className="h-4 w-4" /> Progress updates ({updates.length})</h2>
          <ul className="mt-4 space-y-3">
            {updates.map((u) => (
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
