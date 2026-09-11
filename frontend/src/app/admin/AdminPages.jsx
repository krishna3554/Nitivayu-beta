import React, { useEffect, useState } from 'react';
import { Building2, Send, FileDown, CheckCircle2, Download } from 'lucide-react';
import { EmptyState, PageBack } from '../../components/ui';
import ScalabilityDashboard from '../../components/ScalabilityDashboard';
import { exportTriageReport, exportAdmin, getInvites, revokeInvite } from '../../services/api';
import api from '../../services/api';

export function AdminOrgsPage() {
  const [form, setForm] = useState({ email: '', type: 'university', org: '' });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [invites, setInvites] = useState([]);
  const [loadingInvites, setLoadingInvites] = useState(true);

  const loadInvites = async () => {
    try {
      const { data } = await getInvites();
      setInvites(Array.isArray(data) ? data : []);
    } catch { /* list stays empty; form error surfaces on send */ }
    finally { setLoadingInvites(false); }
  };
  useEffect(() => { loadInvites(); }, []);

  const invite = async (e) => {
    e.preventDefault();
    setSending(true); setNotice(''); setError('');
    try {
      const { data } = await api.post('/admin/invites', { email: form.email, organization_type: form.type, organization_name: form.org });
      setNotice(data?.emailed
        ? `Invite emailed to ${form.email}. It expires in 7 days.`
        : (data?.token
          ? `Invite created for ${form.email} (expires in 7 days). Email is not configured, so copy this one-time token into the invite email: ${data.token}`
          : `Invite sent to ${form.email}. It expires in 7 days and is tracked below.`));
      setForm({ email: '', type: 'university', org: '' });
      loadInvites();
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send that invite.');
    } finally { setSending(false); }
  };

  const revoke = async (inviteId) => {
    try { await revokeInvite(inviteId); loadInvites(); }
    catch (err) { setError(err.response?.data?.detail || 'Could not revoke that invite.'); }
  };

  const pending = invites.filter((i) => i.status === 'pending');

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="type-display-md !text-3xl">Organizations</h1>
      <p className="type-body-md mt-2 text-zinc-500">Invite-only onboarding for universities and CSR desks. Citizens always self-serve — they never need an invite.</p>
      <form onSubmit={invite} className="card mt-5 space-y-4 p-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="type-label-sm">Work email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="iic@university.ac.in" className="input mt-1.5" /></label>
          <label className="type-label-sm">Organization<input required value={form.org} onChange={(e) => setForm({ ...form, org: e.target.value })} placeholder="BIT Mesra / Tata Steel" className="input mt-1.5" /></label>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex gap-1.5" role="group" aria-label="Organization type">
            {['university', 'industry'].map((t) => (
              <button key={t} type="button" onClick={() => setForm({ ...form, type: t })} aria-pressed={form.type === t}
                className={`rounded-md px-3 py-1.5 text-xs font-medium-plus capitalize ${form.type === t ? 'bg-primary-subtle text-primary' : 'bg-surface-muted text-ink-secondary'}`}>{t}</button>
            ))}
          </span>
          <button type="submit" disabled={sending} className="btn-primary ml-auto inline-flex items-center gap-2 !py-2 disabled:opacity-60">
            <Send className="h-3.5 w-3.5" /> {sending ? 'Sending…' : 'Send invite'}
          </button>
        </div>
        {notice && <p className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" />{notice}</p>}
        {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      </form>
      <div className="mt-4">
        {loadingInvites ? (
          <div className="card h-20 animate-pulse" aria-label="Loading invites" />
        ) : !pending.length ? (
          <EmptyState icon={Building2} title="No pending invites — sent invites with status and revoke controls will list here." />
        ) : (
          <ul className="space-y-2">
            {pending.map((i) => (
              <li key={i.invite_id} className="card flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium-plus">{i.email}</p>
                  <p className="mt-0.5 text-xs text-zinc-500 capitalize">{i.organization_type} · {i.organization_name || '—'} · expires {i.expires_at ? new Date(i.expires_at).toLocaleDateString() : '—'}</p>
                </div>
                <button type="button" onClick={() => revoke(i.invite_id)} className="btn-secondary shrink-0 !py-1.5">Revoke</button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function AdminTelemetryPage() {
  return (
    <div>
      <PageBack to="/app/admin" label="Back to organizations" />
      <h1 className="type-display-md mt-3 !text-3xl">Telemetry</h1>
      <p className="type-body-md mt-2 max-w-2xl text-zinc-500">Pipeline health across intake, triage, routing, and funding — every number below reads from the live backend.</p>
      <div className="mt-5"><ScalabilityDashboard bare /></div>
    </div>
  );
}

const EXPORTS = [
  { kind: null, title: 'AI triage report (CSV)', desc: 'Full snapshot: extraction, severity, top-3 matches, status.' },
  { kind: 'sla-log', title: 'SLA & escalation log (CSV)', desc: 'Officer decisions, university responses, warnings, escalations.' },
  { kind: 'routing-pdf', title: 'University routing report (PDF)', desc: 'Category mix plus the routing leaderboard.' },
  { kind: 'audit-jsonl', title: 'System audit log (JSONL)', desc: 'Full audit trail, one event per line.' },
  { kind: 'csr-matrix', title: 'CSR funding matrix (XLSX)', desc: 'Problems × pledged funding for board and audit use.' },
];

export function AdminExportsPage() {
  const [jobs, setJobs] = useState({}); // kind -> {running, result, error}
  const run = async (kind) => {
    const key = kind || 'triage';
    setJobs((j) => ({ ...j, [key]: { running: true, result: null, error: '' } }));
    try {
      const { data } = kind ? await exportAdmin(kind) : await exportTriageReport();
      setJobs((j) => ({ ...j, [key]: { running: false, result: data, error: '' } }));
    } catch (err) {
      setJobs((j) => ({ ...j, [key]: { running: false, result: null, error: err.response?.data?.detail || 'Export failed. Retry in a moment.' } }));
    }
  };
  const openDownload = (url) => {
    try {
      const absolute = url.startsWith('http') ? url : `${window.location.origin}${url}`;
      window.open(absolute, '_blank', 'noopener');
    } catch { /* ignore */ }
  };
  return (
    <div className="mx-auto max-w-3xl">
      <PageBack to="/app/admin" label="Back to organizations" />
      <h1 className="type-display-md mt-3 !text-3xl">Compliance exports</h1>
      <p className="type-body-md mt-2 text-zinc-500">Triage CSVs, SLA logs, routing PDFs, audit JSONL, and CSR matrices — generated on demand and downloadable.</p>
      <div className="mt-5 space-y-3">
        {EXPORTS.map(({ kind, title, desc }) => {
          const key = kind || 'triage';
          const job = jobs[key] || {};
          return (
            <div key={key} className="card p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="font-medium-plus">{title}</h2>
                  <p className="type-body-sm mt-1 text-zinc-500">{desc}</p>
                </div>
                <button onClick={() => run(kind)} disabled={job.running} className="btn-primary inline-flex items-center gap-2 !py-2 disabled:opacity-60">
                  <FileDown className="h-4 w-4" /> {job.running ? 'Generating…' : 'Generate now'}
                </button>
              </div>
              {job.result && (
                <p className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  Wrote {job.result.count ?? '—'} rows.
                  {job.result.download_url && (
                    <button type="button" onClick={() => openDownload(job.result.download_url)} className="inline-flex items-center gap-1 font-medium-plus underline">
                      <Download className="h-3.5 w-3.5" /> Download
                    </button>
                  )}
                </p>
              )}
              {job.error && <p role="alert" className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{job.error}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
