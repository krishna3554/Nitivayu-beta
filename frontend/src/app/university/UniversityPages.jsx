import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Inbox, Users, ImagePlus, Send, Pencil } from 'lucide-react';
import { EmptyState, PageBack, MilestoneBurst, SeverityBadge, SLACountdown, StatusBadge } from '../../components/ui';
import { getUniversityInbox, getUniversityProjects, getUniversityWorkspace, getTeamUpdates, postTeamUpdate, respondToAssignment, submitMilestone, updateTeam } from '../../services/api';
import { useMetaConfig } from '../../lib/meta';

export function UniversityInboxPage() {
  const [inbox, setInbox] = useState([]);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const { config } = useMetaConfig();
  const slaDays = Math.round(config.university_sla_hours / 24);

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
      <p className="type-body-md mt-2 text-zinc-500">Officer-verified challenges matched to your departments. Accept within {slaDays} days — a warning arrives before the deadline.</p>
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
                  <span className="ml-auto"><SLACountdown deadline={item.sla_deadline} totalHours={config.university_sla_hours} /></span>
                </div>
                <h2 className="mt-3 text-lg font-medium-plus">
                  <Link to={`/app/university/inbox/${item.assignment_id}`} className="hover:text-primary hover:underline">{item.problem_title}</Link>
                </h2>
                {item.summary && <p className="type-body-sm mt-1 text-zinc-500">{item.summary}</p>}
                <div className="mt-4 flex items-center justify-between gap-4">
                  <p className="font-mono text-sm text-primary">match {Number(item.match_score).toFixed(3)}</p>
                  <span className="flex gap-2">
                    <Link to={`/app/university/inbox/${item.assignment_id}`} className="btn-secondary !py-2">View details</Link>
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
              <ProjectCard key={p.team_id} project={p} />
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

/** One active project: milestones, evidence submit, team details, updates. */
function ProjectCard({ project: p }) {
  const [project, setProject] = useState(p);
  const [updates, setUpdates] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [showTeamForm, setShowTeamForm] = useState(false);
  const [submitFor, setSubmitFor] = useState(null);

  useEffect(() => { setProject(p); }, [p]);

  const refreshProject = async () => {
    try {
      const { data } = await getUniversityProjects();
      const fresh = (Array.isArray(data) ? data : []).find((x) => x.team_id === p.team_id);
      if (fresh) setProject(fresh);
    } catch { /* keep current card state */ }
  };

  const refreshUpdates = async () => {
    try {
      const { data } = await getTeamUpdates(p.team_id);
      setUpdates(Array.isArray(data) ? data : []);
    } catch { /* history stays as-is; composer error surfaces on submit */ }
  };
  useEffect(() => { refreshUpdates(); }, [p.team_id]);

  const needsTeamDetails = !project.faculty_mentor_name || project.faculty_mentor_name === 'TBD'
    || !project.student_lead_name || project.student_lead_name === 'TBD';

  return (
    <li className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-medium-plus">{project.title || project.problem_title || 'Project team'}</h2>
          <p className="type-body-sm mt-1 text-zinc-500">{project.faculty_mentor_name && `Mentor: ${project.faculty_mentor_name} · `}{project.student_lead_name && `Lead: ${project.student_lead_name}`}</p>
        </div>
        <StatusBadge status={project.status} />
      </div>
      {needsTeamDetails && !showTeamForm && (
        <button type="button" onClick={() => setShowTeamForm(true)} className="btn-secondary mt-3 inline-flex items-center gap-2 !py-2">
          <Pencil className="h-3.5 w-3.5" /> Add mentor & team lead
        </button>
      )}
      {showTeamForm && (
        <TeamDetailsForm
          project={project}
          onSaved={(saved) => { setProject({ ...project, ...saved }); setShowTeamForm(false); refreshProject(); }}
          onCancel={() => setShowTeamForm(false)}
        />
      )}
      {(project.milestones || []).length > 0 && (
        <ol className="mt-4 space-y-2">
          {project.milestones.map((m) => {
            const verified = String(m.status || '').toUpperCase() === 'VERIFIED';
            const submittable = ['PENDING', 'REJECTED'].includes(String(m.status || '').toUpperCase());
            return (
            <li key={m.milestone_id || m.milestone_num} className={`rounded-sm border border-border bg-surface-muted px-3 py-2 text-sm ${verified ? 'relative' : ''}`}>
              {verified && <span aria-hidden className="glow-accent glow-loop" />}
              {verified && <MilestoneBurst />}
              <div className="flex items-center justify-between gap-2">
                <span className="relative z-10">M{m.milestone_num}: {m.title}</span>
                <span className="relative z-10"><StatusBadge status={m.status} /></span>
              </div>
              {submittable && submitFor !== m.milestone_id && (
                <button type="button" onClick={() => setSubmitFor(m.milestone_id)} className="link-inline relative z-10 mt-1.5 !text-xs">Submit evidence for review</button>
              )}
              {submitFor === m.milestone_id && (
                <MilestoneSubmitForm
                  milestone={m}
                  onSubmitted={() => { setSubmitFor(null); refreshProject(); }}
                  onCancel={() => setSubmitFor(null)}
                />
              )}
            </li>
            );
          })}
        </ol>
      )}

      {/* Update history (newest last, like the citizen tracker) */}
      {updates.length > 0 && (
        <div className="mt-4 border-t border-border pt-4">
          <h3 className="type-label-sm text-zinc-500">Progress updates ({updates.length})</h3>
          <ul className="mt-2 space-y-2">
            {updates.map((u) => (
              <li key={u.update_id} className="rounded-sm border border-border bg-surface-muted p-3 text-sm">
                <p>{u.note}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {u.milestone && u.milestone !== 'general' ? `${u.milestone} · ` : ''}{u.created_at ? new Date(u.created_at).toLocaleString() : ''}
                  {u.photo_urls?.length ? ` · ${u.photo_urls.length} photo${u.photo_urls.length > 1 ? 's' : ''}` : ''}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!showForm ? (
        <button type="button" onClick={() => setShowForm(true)} className="btn-secondary mt-4 !py-2">Post project update</button>
      ) : (
        <UpdateComposer
          teamId={project.team_id}
          milestones={project.milestones || []}
          onPosted={(created) => { setUpdates((prev) => [...prev, created]); setShowForm(false); }}
          onCancel={() => setShowForm(false)}
        />
      )}
    </li>
  );
}

/** Team details: mentor, lead, proposal title — fills the TBD auto-created team. */
function TeamDetailsForm({ project, onSaved, onCancel }) {
  const [form, setForm] = useState({
    faculty_mentor_name: project.faculty_mentor_name === 'TBD' ? '' : (project.faculty_mentor_name || ''),
    student_lead_name: project.student_lead_name === 'TBD' ? '' : (project.student_lead_name || ''),
    proposal_title: project.proposal_title || project.title || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async (e) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true); setError('');
    try {
      await updateTeam(project.team_id, {
        faculty_mentor_name: form.faculty_mentor_name || undefined,
        student_lead_name: form.student_lead_name || undefined,
        proposal_title: form.proposal_title || undefined,
      });
      onSaved(form);
    } catch (err) { setError(err.response?.data?.detail || 'Could not save team details.'); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={save} className="mt-3 rounded-sm border border-border bg-surface-muted p-4" aria-label="Team details">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="type-label-sm">Faculty mentor
          <input value={form.faculty_mentor_name} onChange={(e) => setForm({ ...form, faculty_mentor_name: e.target.value })} required placeholder="Prof. Sharma" className="input mt-1.5 bg-white" />
        </label>
        <label className="type-label-sm">Student lead
          <input value={form.student_lead_name} onChange={(e) => setForm({ ...form, student_lead_name: e.target.value })} required placeholder="Priya Kumari" className="input mt-1.5 bg-white" />
        </label>
      </div>
      <label className="type-label-sm mt-3 block">Proposal title
        <input value={form.proposal_title} onChange={(e) => setForm({ ...form, proposal_title: e.target.value })} placeholder="e.g. Sadar Market Drainage Redesign" className="input mt-1.5 bg-white" />
      </label>
      {error && <p role="alert" className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div className="mt-3 flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="btn-secondary !py-2">Cancel</button>
        <button type="submit" disabled={saving} className="btn-primary !py-2 disabled:opacity-60">{saving ? 'Saving…' : 'Save team'}</button>
      </div>
    </form>
  );
}

/** Milestone evidence submit: note + file → officer verification queue. */
function MilestoneSubmitForm({ milestone, onSubmitted, onCancel }) {
  const [note, setNote] = useState('');
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true); setError('');
    try {
      const payload = new FormData();
      if (note.trim()) payload.append('note', note.trim());
      if (file) payload.append('evidence', file, file.name);
      await submitMilestone(milestone.milestone_id, payload);
      onSubmitted();
    } catch (err) { setError(err.response?.data?.detail || 'Could not submit evidence.'); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={submit} className="relative z-10 mt-2 rounded-sm border border-border bg-white p-3" aria-label={`Submit evidence for M${milestone.milestone_num}`}>
      <label className="type-label-sm">Evidence note
        <input value={note} onChange={(e) => setNote(e.target.value.slice(0, 500))} placeholder="What did the team complete?" className="input mt-1.5" />
      </label>
      <label className="type-label-sm mt-2 block">Evidence file <span className="text-zinc-400">(photo, PDF, report)</span>
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="mt-1.5 w-full text-sm" />
      </label>
      {error && <p role="alert" className="mt-2 text-sm text-rose-700">{error}</p>}
      <div className="mt-2 flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="btn-secondary !py-1.5">Cancel</button>
        <button type="submit" disabled={saving} className="btn-primary !py-1.5 disabled:opacity-60">{saving ? 'Submitting…' : 'Submit for review'}</button>
      </div>
    </form>
  );
}

/** Structured update: plain-language note + milestone marker + field photos. */
function UpdateComposer({ teamId, milestones, onPosted, onCancel }) {
  const [note, setNote] = useState('');
  const [milestone, setMilestone] = useState('general');
  const [photos, setPhotos] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (!note.trim() || saving) return;
    setSaving(true); setError('');
    try {
      const payload = new FormData();
      payload.append('note', note.trim());
      payload.append('milestone', milestone);
      [...photos].slice(0, 3).forEach((f) => payload.append('photos', f, f.name));
      const { data } = await postTeamUpdate(teamId, payload);
      onPosted(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not post your update. Try again in a moment.');
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={submit} className="mt-4 rounded-sm border border-border bg-surface-muted p-4" aria-label="Post a project update">
      <label htmlFor={`note-${teamId}`} className="type-label-sm">Progress note <span className="text-zinc-400">(plain language — the citizen reads this)</span></label>
      <textarea
        id={`note-${teamId}`}
        rows={3}
        required
        value={note}
        onChange={(e) => setNote(e.target.value.slice(0, 2000))}
        placeholder="e.g. Ranchi University has completed the baseline water testing for this report. Next: treatment plan design."
        className="input mt-1.5 resize-none bg-white"
      />
      <div className="mt-1 text-right font-mono text-xs text-zinc-400">{note.length}/2000</div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="type-label-sm">Milestone marker
          <select value={milestone} onChange={(e) => setMilestone(e.target.value)} className="input mt-1.5 bg-white">
            <option value="general">General progress</option>
            {(milestones || []).map((m) => (
              <option key={m.milestone_id || m.milestone_num} value={`M${m.milestone_num}`}>
                M{m.milestone_num} — {m.title || `milestone ${m.milestone_num}`}
              </option>
            ))}
          </select>
        </label>
        <label className="type-label-sm">Field photos <span className="text-zinc-400">(up to 3)</span>
          <span className="input mt-1.5 flex items-center gap-2 bg-white">
            <ImagePlus className="h-4 w-4 shrink-0 text-zinc-400" />
            <input type="file" accept="image/*" multiple onChange={(e) => setPhotos(e.target.files || [])} className="w-full text-sm" aria-label="Field work photos" />
          </span>
        </label>
      </div>
      {photos.length > 0 && <p className="type-body-sm mt-1.5 text-zinc-500">{photos.length} photo{photos.length > 1 ? 's' : ''} attached.</p>}
      {error && <p role="alert" className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div className="mt-3 flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="btn-secondary !py-2">Cancel</button>
        <button type="submit" disabled={saving || !note.trim()} className="btn-primary inline-flex items-center gap-2 !py-2 disabled:opacity-60">
          <Send className="h-3.5 w-3.5" /> {saving ? 'Posting…' : 'Post update'}
        </button>
      </div>
      <p className="type-body-sm mt-2 text-zinc-400">Posted updates appear on the citizen’s tracker and in the officer audit trail.</p>
    </form>
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
