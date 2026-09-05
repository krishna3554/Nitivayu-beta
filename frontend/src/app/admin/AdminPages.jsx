import React, { useState } from 'react';
import { Building2, Send, FileDown, CheckCircle2 } from 'lucide-react';
import { EmptyState } from '../../components/ui';
import ScalabilityDashboard from '../../components/ScalabilityDashboard';
import { exportTriageReport } from '../../services/api';
import api from '../../services/api';

export function AdminOrgsPage() {
  const [form, setForm] = useState({ email: '', type: 'university', org: '' });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);

  const invite = async (e) => {
    e.preventDefault();
    setSending(true); setNotice(''); setError('');
    try {
      await api.post('/admin/invites', { email: form.email, organization_type: form.type, organization_name: form.org });
      setNotice(`Invite sent to ${form.email}. It expires in 7 days and is tracked below.`);
      setForm({ email: '', type: 'university', org: '' });
    } catch (err) {
      if (err.response?.status === 404) setError('Invite management connects with institutional hardening (Phase 6). Provision accounts directly in the database for this demo.');
      else setError(err.response?.data?.detail || 'Could not send that invite.');
    } finally { setSending(false); }
  };

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
      <div className="mt-4"><EmptyState icon={Building2} title="No pending invites on this build yet — sent invites with status and revoke controls will list here." /></div>
    </div>
  );
}

export function AdminTelemetryPage() {
  return (
    <div>
      <h1 className="type-display-md !text-3xl">Telemetry</h1>
      <p className="type-body-md mt-2 max-w-2xl text-zinc-500">Pipeline health across intake, triage, routing, and funding. Full Prometheus/Grafana wiring lands with realtime + observability (Phase 5).</p>
      <div className="mt-5"><ScalabilityDashboard bare /></div>
    </div>
  );
}

export function AdminExportsPage() {
  const [state, setState] = useState({ running: false, result: null, error: '' });
  const run = async () => {
    setState({ running: true, result: null, error: '' });
    try {
      const { data } = await exportTriageReport();
      setState({ running: false, result: data, error: '' });
    } catch (err) { setState({ running: false, result: null, error: err.response?.data?.detail || 'Export failed. Retry in a moment.' }); }
  };
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="type-display-md !text-3xl">Compliance exports</h1>
      <p className="type-body-md mt-2 text-zinc-500">Triage CSVs, SLA logs, routing PDFs, audit JSONL, and CSR matrices — versioned and downloadable. Object-storage signed URLs arrive with compliance hardening (Phase 7).</p>
      <div className="card mt-5 flex flex-wrap items-center justify-between gap-4 p-6">
        <div>
          <h2 className="font-medium-plus">AI triage report (CSV)</h2>
          <p className="type-body-sm mt-1 text-zinc-500">Full snapshot: extraction, severity, top-3 matches, status.</p>
        </div>
        <button onClick={run} disabled={state.running} className="btn-primary inline-flex items-center gap-2 !py-2 disabled:opacity-60">
          <FileDown className="h-4 w-4" /> {state.running ? 'Generating…' : 'Generate now'}
        </button>
      </div>
      {state.result && <p className="card mt-4 border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">Wrote {state.result.path || 'report'} ({state.result.count ?? '—'} rows).</p>}
      {state.error && <p role="alert" className="card mt-4 border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{state.error}</p>}
      <ul className="mt-4 space-y-2 text-sm text-zinc-500">
        {['SLA & escalation log — daily append', 'University routing report (PDF) — weekly', 'System audit log (JSONL) — daily append', 'CSR funding matrix (XLSX) — monthly'].map((f) => (
          <li key={f} className="panel-flat px-4 py-3">{f}</li>
        ))}
      </ul>
    </div>
  );
}
