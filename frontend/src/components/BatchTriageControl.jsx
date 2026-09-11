import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Play, Settings, Calendar, Clock, CheckCircle, XCircle } from 'lucide-react';
import { getBatchStatus, getBatchHistory, runBatch, updateBatchSchedule } from '../services/api';
import { useAuth } from '../lib/auth';

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function fmtDuration(s) {
  if (s == null) return '—';
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export default function BatchTriageControl() {
  const { session } = useAuth();
  const [schedule, setSchedule] = useState(null);
  const [history, setHistory] = useState([]);
  const [jobId, setJobId] = useState('');
  const [events, setEvents] = useState([]);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [loadError, setLoadError] = useState('');
  const [form, setForm] = useState({ active_cadence: 'weekly', cron_expression: '0 0 * * 0', monthly_macro_cron: '0 0 1 * *' });
  const esRef = useRef(null);

  const loadAll = useCallback(async () => {
    try {
      const [{ data: sched }, { data: hist }] = await Promise.all([getBatchStatus(), getBatchHistory()]);
      setSchedule(sched);
      setHistory(Array.isArray(hist) ? hist : []);
      setForm({
        active_cadence: sched?.active_cadence || 'weekly',
        cron_expression: sched?.cron_expression || '0 0 * * 0',
        monthly_macro_cron: sched?.monthly_macro_cron || '0 0 1 * *',
      });
      setLoadError('');
    } catch (err) {
      setLoadError(err.response?.data?.detail || 'Could not load batch status.');
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => () => esRef.current?.close(), []);

  const pushEvent = (kind, data) => setEvents((prev) => [...prev.slice(-49), { at: new Date().toLocaleTimeString(), kind, data }]);

  const handleRun = async () => {
    if (!window.confirm('Start a real weekly batch run now? It re-triages all unprocessed intake.')) return;
    setRunning(true); setMessage(''); setEvents([]);
    esRef.current?.close();
    try {
      const { data } = await runBatch({ cadence_type: schedule?.active_cadence === 'continuous' ? 'weekly' : (schedule?.active_cadence || 'weekly'), include_unassigned_only: true });
      setJobId(data.batch_workflow_id);
      pushEvent('started', { batch_id: data.batch_workflow_id });
      const es = new EventSource(`${data.stream_url}?token=${encodeURIComponent(session?.token || '')}`);
      esRef.current = es;
      for (const kind of ['started', 'progress', 'done', 'error', 'timeout']) {
        es.addEventListener(kind, (e) => {
          let payload = {};
          try { payload = JSON.parse(e.data || '{}'); } catch { payload = { raw: e.data }; }
          pushEvent(kind, payload);
          if (kind === 'done' || kind === 'error' || kind === 'timeout') {
            es.close(); setRunning(false); loadAll();
            if (kind === 'done') setMessage(`Batch finished: ${payload.processed_count ?? payload.processed ?? 0} routed${payload.duplicates ? `, ${payload.duplicates} duplicates merged` : ''}.`);
            else setMessage(payload.message || 'Batch stream ended with an error.');
          }
        });
      }
      es.onerror = () => { /* terminal events close the stream; silent otherwise */ };
    } catch (error) {
      setRunning(false);
      setMessage(error.response?.data?.detail || 'Unable to start batch.');
    }
  };

  const handleSaveSchedule = async (e) => {
    e.preventDefault();
    setSaving(true); setMessage('');
    try {
      const { data } = await updateBatchSchedule(form);
      setMessage(data.schedule_error || data.message || 'Schedule updated.');
      loadAll();
    } catch (error) {
      setMessage(error.response?.data?.detail || 'Could not save the schedule.');
    } finally { setSaving(false); }
  };

  const statusChip = (status) => {
    const s = String(status || '').toUpperCase();
    if (s === 'COMPLETED' || s === 'SUCCESS') return <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-md border border-emerald-100"><CheckCircle className="w-3 h-3" /> Completed</span>;
    if (s === 'RUNNING' || s === 'STARTED') return <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-md border border-indigo-100"><span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" /> Running</span>;
    return <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-50 text-rose-700 text-xs font-semibold rounded-md border border-rose-100"><XCircle className="w-3 h-3" /> {s || 'Unknown'}</span>;
  };

  return (
    <div className="max-w-5xl mx-auto p-6 mt-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Batch Triage Control</h1>
        <p className="text-zinc-600 mt-1">Weekly re-triage of all unprocessed intake: extract → cluster → route → reports.</p>
      </div>

      {loadError && <p role="alert" className="mb-5 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{loadError}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <form onSubmit={handleSaveSchedule} className="col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-zinc-900 flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary" /> Cadence
            </h2>
            <span className="px-3 py-1 bg-slate-100 text-zinc-600 text-xs font-bold rounded-full uppercase tracking-wider">
              {schedule?.schedule_status === 'scheduled' ? 'Scheduled' : schedule?.schedule_status === 'temporal-unreachable' ? 'No scheduler' : 'Manual'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <label className="text-sm font-medium text-zinc-700">Mode
              <select value={form.active_cadence} onChange={(e) => setForm({ ...form, active_cadence: e.target.value })} className="input mt-1.5">
                <option value="weekly">Weekly batch</option>
                <option value="continuous">Continuous (real-time only)</option>
              </select>
            </label>
            <label className="text-sm font-medium text-zinc-700">Weekly cron (UTC)
              <input value={form.cron_expression} onChange={(e) => setForm({ ...form, cron_expression: e.target.value })} className="input mt-1.5 font-mono" placeholder="0 0 * * 0" />
            </label>
            <label className="text-sm font-medium text-zinc-700">Monthly cron (UTC)
              <input value={form.monthly_macro_cron} onChange={(e) => setForm({ ...form, monthly_macro_cron: e.target.value })} className="input mt-1.5 font-mono" placeholder="0 0 1 * *" />
            </label>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="type-body-sm text-zinc-500">
              Backlog: <strong className="text-ink">{schedule?.pending_count ?? '—'}</strong> unprocessed
              {schedule?.next_run_utc ? <> · next run <span className="font-mono">{fmtDate(schedule.next_run_utc)}</span></> : null}
            </p>
            <button type="submit" disabled={saving} className="btn-secondary !py-2 disabled:opacity-60">{saving ? 'Saving…' : 'Save schedule'}</button>
          </div>
        </form>

        <div className="card flex flex-col justify-center p-6">
          <h3 className="type-label-sm mb-4 text-zinc-500">Manual override</h3>
          <button
            onClick={handleRun}
            disabled={running}
            className="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-60"
          >
            {running ? (
              <><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Running batch…</>
            ) : (
              <><Play className="w-5 h-5" /> Run batch now</>
            )}
          </button>
          <p className="type-body-sm mt-3 text-center text-zinc-400">Spawns a Temporal workflow immediately</p>
        </div>
      </div>
      {message && <p className="mb-5 text-sm text-primary">{message}</p>}

      {(running || events.length > 0) && (
        <div className="card mb-8 p-6" aria-live="polite">
          <h2 className="text-lg font-semibold text-zinc-900">Live progress {jobId && <span className="font-mono text-sm text-zinc-500">{jobId}</span>}</h2>
          <ul className="mt-3 max-h-56 space-y-1.5 overflow-auto font-mono text-xs text-zinc-600">
            {events.map((e, i) => (
              <li key={i}><span className="text-zinc-400">{e.at}</span> <span className="font-semibold text-primary">{e.kind}</span> {JSON.stringify(e.data).slice(0, 220)}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-zinc-900">Run History</h2>
        </div>
        {history.length === 0 ? (
          <p className="type-body-sm p-6 text-zinc-500">No batch runs yet — trigger the first one above.</p>
        ) : (
        <table className="w-full text-left">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Run ID</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Started</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Routed</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Duration</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {history.map((row) => (
              <tr key={row.batch_id} className="hover:bg-slate-50 transition-colors" title={row.error || (row.csv_path ? `CSV: ${row.csv_path}` : '')}>
                <td className="p-4 text-sm font-medium text-zinc-900 font-mono">{String(row.batch_id).replace('batch-triage-', '')}</td>
                <td className="p-4 text-sm text-zinc-600 flex items-center gap-2"><Calendar className="w-4 h-4 text-zinc-400" /> {fmtDate(row.started_at)}</td>
                <td className="p-4 text-sm font-medium text-zinc-900">{row.processed}{row.duplicates ? <span className="text-zinc-400"> ({row.duplicates} dup)</span> : null}{row.failed ? <span className="text-rose-600"> · {row.failed} failed</span> : null}</td>
                <td className="p-4 text-sm text-zinc-600 flex items-center gap-1"><Clock className="w-3 h-3 text-zinc-400" /> {fmtDuration(row.duration_seconds)}</td>
                <td className="p-4">{statusChip(row.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>
    </div>
  );
}
