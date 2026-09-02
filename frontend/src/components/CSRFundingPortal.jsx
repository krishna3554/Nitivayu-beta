import React, { useState } from 'react';
import { IndianRupee, Heart, MapPin, Building, ArrowRight } from 'lucide-react';
import { createCsrPledge, getCSRChallenges } from '../services/api';

export default function CSRFundingPortal() {
  const [showPledgeModal, setShowPledgeModal] = useState(false);
  const [selectedChallenge, setSelectedChallenge] = useState(null);
  const [pledgeAmount, setPledgeAmount] = useState('');
  const [challenges, setChallenges] = useState([]);
  React.useEffect(() => { getCSRChallenges().then(({ data }) => setChallenges(data.map(item => ({ id: item.problem_id, title: item.title, category: item.category, district: 'Jharkhand', budget: 'To be scoped', university: 'Pending assignment', progress: 0 })))).catch(console.error); }, []);

  const submitPledge = async () => { try { await createCsrPledge({ problem_id: selectedChallenge.id, pledged_amount_inr: Number(pledgeAmount) }); setShowPledgeModal(false); setPledgeAmount(''); } catch (error) { alert(error.response?.data?.detail || 'Unable to record pledge.'); } };

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
            <p className="text-3xl font-bold">₹4.2 Cr</p>
          </div>
          <div className="w-px bg-sky-700"></div>
          <div>
            <p className="text-sky-200 text-xs font-semibold uppercase tracking-wider mb-1">Projects Funded</p>
            <p className="text-3xl font-bold">34</p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-zinc-900">Fundable Projects</h2>
        <div className="flex gap-2">
          <select className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white">
            <option>All Sectors</option>
            <option>Water & Sanitation</option>
            <option>Education</option>
          </select>
          <select className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg bg-white">
            <option>All Districts</option>
            <option>Patna</option>
            <option>Gaya</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {challenges.map(c => (
          <div key={c.id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
            <div className="p-5 flex-1">
              <div className="flex justify-between items-start mb-4">
                <span className="px-2.5 py-1 bg-sky-50 text-sky-700 text-xs font-semibold rounded-md border border-sky-100">{c.category}</span>
                <span className="flex items-center text-xs font-medium text-zinc-500 gap-1"><MapPin className="w-3 h-3" /> {c.district}</span>
              </div>
              <h3 className="text-lg font-bold text-zinc-900 mb-2 leading-snug">{c.title}</h3>
              <p className="text-sm text-zinc-600 flex items-center gap-1.5 mb-4">
                <Building className="w-4 h-4 text-zinc-400" /> Executed by: <span className="font-medium text-zinc-900">{c.university}</span>
              </p>
              
              <div className="mb-2 flex justify-between text-sm font-medium">
                <span className="text-zinc-500">Required: <span className="text-zinc-900">{c.budget}</span></span>
                <span className="text-sky-600">{c.progress}% Funded</span>
              </div>
              <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-sky-500 rounded-full" style={{ width: `${c.progress}%` }}></div>
              </div>
            </div>
            
            <div className="p-4 bg-slate-50 border-t border-slate-100 flex justify-between items-center">
              <button className="text-sm font-medium text-zinc-600 hover:text-zinc-900 transition-colors">Details</button>
              <button 
                onClick={() => { setSelectedChallenge(c); setShowPledgeModal(true); }}
                className="px-4 py-2 bg-zinc-900 text-white text-sm font-medium rounded-lg hover:bg-zinc-800 transition-colors flex items-center gap-1"
              >
                <Heart className="w-4 h-4" /> Pledge
              </button>
            </div>
          </div>
        ))}
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
                <input value={pledgeAmount} onChange={(event) => setPledgeAmount(event.target.value)} type="number" className="w-full pl-10 pr-4 py-3 text-lg border border-slate-300 rounded-lg focus:ring-2 focus:ring-sky-500 outline-none" placeholder="100000" />
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
