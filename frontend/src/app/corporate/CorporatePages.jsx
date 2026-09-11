import React, { useEffect, useRef, useState } from 'react';
import { Compass, Wallet, IndianRupee, MapPin, Building } from 'lucide-react';
import { EmptyState, MomentGlow, MilestoneBurst, PageBack, SeverityBadge, StatusBadge } from '../../components/ui';
import { createCsrPledge, getCSRChallenges, getCSRPledges, getIndustryImpact, exportMonthlyMatrix } from '../../services/api';

export function formatINR(amount) {
  const value = Number(amount) || 0;
  if (value >= 10000000) return `₹${(value / 10000000).toFixed(1)} Cr`;
  if (value >= 100000) return `₹${(value / 100000).toFixed(1)} L`;
  return `₹${value.toLocaleString('en-IN')}`;
}

function useCsrData() {
  const [challenges, setChallenges] = useState([]);
  const [pledges, setPledges] = useState([]);
  const [summary, setSummary] = useState({ total_pledged_inr: 0, projects_funded: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);
  const load = async () => {
    setLoading(true); setError('');
    try {
      const [c, p] = await Promise.all([getCSRChallenges(), getCSRPledges()]);
      if (!mounted.current) return;
      setChallenges(Array.isArray(c.data) ? c.data : []);
      setPledges(p.data.pledges || []);
      setSummary({ total_pledged_inr: p.data.total_pledged_inr || 0, projects_funded: p.data.projects_funded || 0 });
    } catch (err) {
      if (!mounted.current) return;
      const timedOut = err?.code === 'ECONNABORTED';
      setError(timedOut ? 'The request timed out. Check your connection and retry.' : (err.response?.data?.detail || 'Unable to load CSR data. Sign in again if this persists.'));
    }
    finally { if (mounted.current) setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  return { challenges, pledges, summary, loading, error, reload: load };
}

export function CorporateOpportunitiesPage() {
  const { challenges, summary, loading, error, reload } = useCsrData();
  const [filter, setFilter] = useState('All sectors');
  const [selected, setSelected] = useState(null);
  const [amount, setAmount] = useState('');
  const [notice, setNotice] = useState('');

  const sectors = ['All sectors', ...new Set(challenges.map((c) => c.category).filter(Boolean))];
  const visible = challenges.filter((c) => filter === 'All sectors' || c.category === filter);

  const pledge = async () => {
    const value = Number(amount);
    if (!value || value <= 0) { setNotice('Enter a pledge amount above ₹0.'); return; }
    try {
      await createCsrPledge({ problem_id: selected.problem_id, pledged_amount_inr: value });
      setSelected(null); setAmount('');
      setNotice(`Pledge of ${formatINR(value)} recorded. It disburses against verified milestones.`);
      reload();
    } catch (err) { setNotice(err.response?.data?.detail || 'Unable to record your pledge.'); }
  };

  return (
    <div>
      <div className="rounded-md bg-ink p-6 text-white md:p-8">
        <h1 className="type-display-md !text-3xl">Fund what you can verify.</h1>
        <p className="type-body-md mt-2 max-w-xl text-white/70">Only officer-routed, university-backed challenges appear here — every rupee links to milestones, not promises.</p>
        <p className="mt-4 text-sm text-white/60">Committed so far: <strong className="text-white">{loading ? <span className="inline-block h-4 w-20 animate-pulse rounded-sm bg-white/20 align-middle" aria-label="Loading totals" /> : formatINR(summary.total_pledged_inr)}</strong> across <strong className="text-white">{loading ? <span className="inline-block h-4 w-8 animate-pulse rounded-sm bg-white/20 align-middle" aria-label="Loading count" /> : summary.projects_funded}</strong> projects</p>
      </div>

      {notice && (notice.startsWith('Pledge of') ? (
        <MomentGlow className="mt-4">
          <div className="relative card border-emerald-200 bg-emerald-50 p-5 text-center" role="status">
            <MilestoneBurst />
            <p className="font-medium-plus text-emerald-900">Pledge confirmed</p>
            <p className="type-body-sm mt-1 text-emerald-700">{notice}</p>
          </div>
        </MomentGlow>
      ) : (
        <p className="card mt-4 border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{notice}</p>
      ))}
      {error && <p className="card mt-4 border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error} <button onClick={reload} className="font-medium-plus underline">Retry</button></p>}

      <div className="mb-4 mt-6 flex items-center justify-between">
        <h2 className="text-lg font-medium-plus">Opportunities</h2>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="input !w-auto !py-2 text-sm" aria-label="Filter by sector">
          {sectors.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

      {loading ? <div className="grid gap-4 md:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="card h-56 animate-pulse" />)}</div>
      : !visible.length ? <EmptyState icon={Compass} title="No fundable projects right now — officer-routed challenges will appear here." />
      : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((c) => (
            <article key={c.problem_id} className="card flex flex-col p-5">
              <div className="flex items-start justify-between gap-2">
                <span className="tag-chip !text-xs">{c.category}</span>
                {c.district && <span className="flex items-center gap-1 text-xs text-zinc-500"><MapPin className="h-3 w-3" />{c.district}</span>}
              </div>
              <h3 className="mt-3 font-medium-plus leading-snug">{c.title}</h3>
              <p className="type-body-sm mt-1 line-clamp-2 text-zinc-500">{c.description}</p>
              <p className="mt-2 flex items-center gap-1.5 text-sm text-zinc-500"><Building className="h-4 w-4 text-zinc-400" />{c.university || <em>Awaiting university offer</em>}</p>
              <div className="mt-3 flex items-center gap-2">
                <SeverityBadge value={c.severity} />
                <StatusBadge status={c.status} />
                <span className="ml-auto text-sm text-zinc-500">Pledged <strong className="text-ink">{formatINR(c.pledged_amount_inr)}</strong></span>
              </div>
              <button onClick={() => { setSelected(c); setNotice(''); }} className="btn-primary mt-4">Pledge funding</button>
            </article>
          ))}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" aria-label="Pledge funding" onClick={() => setSelected(null)}>
          <div className="w-full max-w-md rounded-md bg-white p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-medium-plus">Pledge funding</h3>
            <p className="type-body-sm mt-1 text-zinc-500">{selected.title}</p>
            <label className="type-label-sm mt-5 block">Pledge amount (₹)
              <span className="relative mt-1.5 block">
                <IndianRupee className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
                <input value={amount} onChange={(e) => setAmount(e.target.value)} type="number" min="1" placeholder="100000" className="input pl-9 text-lg" />
              </span>
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setSelected(null)} className="btn-secondary !py-2">Cancel</button>
              <button onClick={pledge} disabled={!amount} className="btn-primary !py-2 disabled:opacity-50">Confirm pledge</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function CorporatePortfolioPage() {
  const { pledges, summary, loading } = useCsrData();
  return (
    <div className="mx-auto max-w-4xl">
      <PageBack to="/app/corporate" label="Back to opportunities" />
      <h1 className="type-display-md mt-3 !text-3xl">Portfolio</h1>
      <p className="type-body-md mt-2 text-zinc-500">
        {loading ? 'Loading your pledges…' : `You have committed ${formatINR(summary.total_pledged_inr)} across ${summary.projects_funded} projects.`}
      </p>
      <div className="card mt-5 overflow-hidden">
        {!pledges.length && !loading ? <div className="p-6"><EmptyState icon={Wallet} title="No pledges yet — fund an opportunity and your disbursement history appears here." actionLabel="Browse opportunities" actionTo="/app/corporate" /></div>
        : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-white">
              <tr>{['Project', 'Amount', 'Status', 'Date'].map((h) => <th key={h} className="type-caption p-3 text-zinc-400">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-border">
              {pledges.map((p) => (
                <tr key={p.id}>
                  <td className="p-3 font-medium-plus">{p.problem_title || String(p.problem_id).slice(0, 8)}</td>
                  <td className="p-3">{formatINR(p.amount)}</td>
                  <td className="p-3"><StatusBadge status={p.status} /></td>
                  <td className="p-3 text-zinc-500">{p.created_at ? new Date(p.created_at).toLocaleDateString('en-IN') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function CorporateImpactPage() {
  const { pledges, summary } = useCsrData();
  const [impact, setImpact] = useState(null);
  const [matrix, setMatrix] = useState({ running: false, url: '', error: '' });
  useEffect(() => { getIndustryImpact().then(({ data }) => setImpact(data)).catch(() => {}); }, []);
  const disbursed = pledges.filter((p) => ['DISBURSED', 'COMPLETED'].includes(String(p.status).toUpperCase())).length;

  const downloadMatrix = async () => {
    setMatrix({ running: true, url: '', error: '' });
    try {
      const { data } = await exportMonthlyMatrix();
      setMatrix({ running: false, url: data?.download_url || '', error: data?.download_url ? '' : 'Export generated but no download link was returned.' });
      if (data?.download_url) {
        const absolute = data.download_url.startsWith('http') ? data.download_url : `${window.location.origin}${data.download_url}`;
        window.open(absolute, '_blank', 'noopener');
      }
    } catch (err) { setMatrix({ running: false, url: '', error: err.response?.data?.detail || 'Export failed. Retry in a moment.' }); }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageBack to="/app/corporate" label="Back to opportunities" />
      <h1 className="type-display-md mt-3 !text-3xl">Impact reports</h1>
      <p className="type-body-md mt-2 text-zinc-500">Monthly funding matrices map your focus areas to validated challenges — exportable for board and audit use.</p>
      <div className="card mt-5 space-y-3 p-6">
        <ImpactRow k="Total committed" v={formatINR(summary.total_pledged_inr)} />
        <ImpactRow k="Projects funded" v={String(impact?.projects_funded ?? summary.projects_funded)} />
        <ImpactRow k="Disbursed / completed" v={String(disbursed)} />
        <ImpactRow k="Milestones verified" v={String(impact?.milestones_verified ?? '—')} />
        <ImpactRow k="Districts reached" v={(impact?.districts_reached || []).join(', ') || '—'} />
        <div className="flex items-center justify-between gap-6 pt-1">
          <dt className="type-label-sm text-zinc-500">Monthly matrix (XLSX)</dt>
          <dd><button type="button" onClick={downloadMatrix} disabled={matrix.running} className="btn-secondary !py-2 disabled:opacity-60">{matrix.running ? 'Generating…' : 'Download'}</button></dd>
        </div>
        {matrix.error && <p role="alert" className="text-sm text-rose-700">{matrix.error}</p>}
      </div>
    </div>
  );
}

function ImpactRow({ k, v }) {
  return (
    <div className="flex justify-between gap-6 border-b border-border pb-3 last:border-0 last:pb-0">
      <dt className="type-label-sm text-zinc-500">{k}</dt>
      <dd className="text-right text-sm font-medium-plus">{v}</dd>
    </div>
  );
}
