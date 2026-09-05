import React, { useState } from 'react';
import { IndianRupee, Heart, MapPin, Building } from 'lucide-react';
import { createCsrPledge, getCSRChallenges, getCSRPledges } from '../services/api';

function formatINR(amount) {
  const value = Number(amount) || 0;
  if (value >= 10000000) return `₹${(value / 10000000).toFixed(1)} Cr`;
  if (value >= 100000) return `₹${(value / 100000).toFixed(1)} L`;
  return `₹${value.toLocaleString('en-IN')}`;
}

export default function CSRFundingPortal() {
  const [showPledgeModal, setShowPledgeModal] = useState(false);
  const [selectedChallenge, setSelectedChallenge] = useState(null);
  const [pledgeAmount, setPledgeAmount] = useState('');
  const [challenges, setChallenges] = useState([]);
  const [pledges, setPledges] = useState([]);
  const [summary, setSummary] = useState({ total_pledged_inr: 0, projects_funded: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sectorFilter, setSectorFilter] = useState('All Sectors');

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const [challengesRes, pledgesRes] = await Promise.all([getCSRChallenges(), getCSRPledges()]);
      setChallenges(challengesRes.data.map(item => {
        const pledged = Number(item.pledged_amount_inr) || 0;
        const goal = 500000;
        return {
          id: item.problem_id,
          title: item.title,
          description: item.description,
          category: item.category,
          severity: item.severity,
          district: item.district || 'Jharkhand',
          university: item.university || 'Pending assignment',
          status: item.status,
          pledged,
          progress: Math.min(100, Math.round((pledged / goal) * 100)),
        };
      }));
      setPledges(pledgesRes.data.pledges || []);
      setSummary({
        total_pledged_inr: pledgesRes.data.total_pledged_inr || 0,
        projects_funded: pledgesRes.data.projects_funded || 0,
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load CSR data. Please sign in again.');
    } finally {
      setLoading(false);
    }
  };
  React.useEffect(() => { loadData(); }, []);

  const submitPledge = async () => {
    const amount = Number(pledgeAmount);
    if (!amount || amount <= 0) { setNotice('Please enter a valid pledge amount.'); return; }
    try {
      await createCsrPledge({ problem_id: selectedChallenge.id, pledged_amount_inr: amount });
      setShowPledgeModal(false);
      setPledgeAmount('');
      setNotice(`Pledge of ${formatINR(amount)} recorded for "${selectedChallenge.title}".`);
      await loadData();
    } catch (error) {
      setNotice(error.response?.data?.detail || 'Unable to record pledge.');
    }
  };

  const visibleChallenges = challenges.filter(c => sectorFilter === 'All Sectors' || c.category === sectorFilter);
  const sectors = ['All Sectors', ...new Set(challenges.map(c => c.category))];

  return (
    <div className="max-w-7xl mx-auto p-6 mt-6">
      {/* Header Dashboard */}
      <div className="bg-sky-900 rounded-2xl p-8 mb-8 text-white flex justify-between items-center shadow-lg">
        <div>
          <h1 className="text-3xl font-bold mb-2">Corporate Social Responsibility</h1>
          <p className="text-sky-100 max-w-xl text-sm leading-relaxed">Direct your CSR funds to validated civic innovation projects driven by top universities. Full transparency and milestone-based disbursement.</p>
        </div>
        <div className="flex gap-6 text-right">
          <div>
            <p className="text-sky-200 text-xs font-semibold uppercase tracking-wider mb-1">Total Pledged</p>
            <p className="text-3xl font-bold">{loading ? '…' : formatINR(summary.total_pledged_inr)}</p>
          </div>
          <div className="w-px bg-sky-700"></div>
          <div>
            <p className="text-sky-200 text-xs font-semibold uppercase tracking-wider mb-1">Projects Funded</p>
            <p className="text-3xl font-bold">{loading ? '…' : summary.projects_funded}</p>
          </div>
        </div>
      </div>

      {error && <div className="mb-6 p-4 bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-xl">{error} <button onClick={loadData} className="ml-2 font-semibold underline">Retry</button></div>}
      {notice && <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-xl">{notice}</div>}

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-zinc-900">Fundable Projects</h2>
        <div className="flex gap-2">
          <select value={sectorFilter} onChange={(e) => setSectorFilter(e.target.value)} className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white">
            {sectors.map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map(i => <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 h-56 animate-pulse"><div className="h-4 bg-slate-100 rounded w-1/3 mb-4"></div><div className="h-5 bg-slate-100 rounded w-3/4 mb-2"></div><div className="h-4 bg-slate-100 rounded w-full"></div></div>)}
        </div>
      ) : visibleChallenges.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-sm text-zinc-500">No fundable projects right now. Officer-routed challenges will appear here.</div>
      ) : (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {visibleChallenges.map(c => (
          <div key={c.id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
            <div className="p-5 flex-1">
              <div className="flex justify-between items-start mb-4">
                <span className="px-2.5 py-1 bg-sky-50 text-sky-700 text-xs font-semibold rounded-md border border-sky-100">{c.category}</span>
                <span className="flex items-center text-xs font-medium text-zinc-500 gap-1"><MapPin className="w-3 h-3" /> {c.district}</span>
              </div>
              <h3 className="text-lg font-bold text-zinc-900 mb-2 leading-snug">{c.title}</h3>
              <p className="text-sm text-zinc-600 line-clamp-2 mb-3">{c.description}</p>
              <p className="text-sm text-zinc-600 flex items-center gap-1.5 mb-4">
                <Building className="w-4 h-4 text-zinc-400" /> Executed by: <span className="font-medium text-zinc-900">{c.university}</span>
              </p>

              <div className="mb-2 flex justify-between text-sm font-medium">
                <span className="text-zinc-500">Pledged: <span className="text-zinc-900">{formatINR(c.pledged)}</span></span>
                <span className="text-sky-600">{c.progress}% Funded</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-sky-500 rounded-full transition-all" style={{ width: `${c.progress}%` }}></div>
              </div>
            </div>

            <div className="p-4 bg-slate-50 border-t border-slate-100 flex justify-between items-center">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">{c.status}</span>
              <button
                onClick={() => { setSelectedChallenge(c); setShowPledgeModal(true); setNotice(''); }}
                className="px-4 py-2 bg-zinc-900 text-white text-sm font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-1"
              >
                <Heart className="w-4 h-4" /> Pledge
              </button>
            </div>
          </div>
        ))}
      </div>
      )}

      {/* My Pledges / Bidding history */}
      <div className="mt-10">
        <h2 className="text-xl font-bold text-zinc-900 mb-4">My Pledges</h2>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          {pledges.length === 0 ? (
            <p className="p-6 text-sm text-zinc-500 text-center">No pledges yet. Fund a project above to see your bidding history here.</p>
          ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="p-3 font-semibold text-zinc-500">Project</th>
                <th className="p-3 font-semibold text-zinc-500">Amount</th>
                <th className="p-3 font-semibold text-zinc-500">Status</th>
                <th className="p-3 font-semibold text-zinc-500">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pledges.map(p => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="p-3 font-medium text-zinc-900">{p.problem_title || p.problem_id.slice(0, 8)}</td>
                  <td className="p-3 text-zinc-700">{formatINR(p.amount)}</td>
                  <td className="p-3"><span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-md border border-emerald-100">{p.status}</span></td>
                  <td className="p-3 text-zinc-500">{p.created_at ? new Date(p.created_at).toLocaleDateString('en-IN') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </div>
      </div>

      {showPledgeModal && (
        <div className="fixed inset-0 bg-zinc-900/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-zinc-900 mb-1">Pledge Funding</h3>
            <p className="text-sm text-zinc-600 mb-6">{selectedChallenge?.title}</p>

            <div className="mb-6">
              <label className="block text-sm font-medium text-zinc-900 mb-2">Pledge Amount (₹)</label>
              <div className="relative">
                <IndianRupee className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
                <input value={pledgeAmount} onChange={(event) => setPledgeAmount(event.target.value)} type="number" min="1" className="w-full pl-10 pr-4 py-3 text-lg border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none" placeholder="100000" />
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <button onClick={() => setShowPledgeModal(false)} className="px-4 py-2 text-sm font-medium text-zinc-600 hover:bg-slate-100 rounded-lg transition-colors">Cancel</button>
              <button disabled={!pledgeAmount} onClick={submitPledge} className="px-4 py-2 text-sm font-medium bg-sky-600 text-white rounded-lg hover:bg-sky-700 transition-colors disabled:opacity-50">Confirm Pledge</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
