import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Check, Clock, AlertCircle, RefreshCw, ChevronRight } from 'lucide-react';
import { getComplaint } from '../services/api';

export default function LiveTrackingCard() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [lastRefreshed, setLastRefreshed] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const loadStatus = async () => {
      try {
        const response = await getComplaint(token);
        setData(response.data);
        setError('');
        setLastRefreshed(new Date().toLocaleTimeString());
      } catch (err) {
        setError(err.response?.data?.detail || 'We could not find this tracking token.');
      }
    };
    loadStatus();
    const timer = setInterval(() => {
      loadStatus();
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  const stages = [
    { id: 'Submitted', label: 'Submitted' },
    { id: 'Triaging', label: 'AI Triaging' },
    { id: 'Officer Review', label: 'Officer Review' },
    { id: 'Routing', label: 'Routed to University' },
    { id: 'University Working', label: 'Under Work' },
    { id: 'Completed', label: 'Resolved' }
  ];

  const statusMap = { PENDING_TRIAGE: 'Triaging', TRIAGING: 'Triaging', PENDING_OFFICER_REVIEW: 'Officer Review', ROUTED: 'Routing', ACCEPTED: 'University Working', COMPLETED: 'Completed', REJECTED: 'Completed' };
  const currentIdx = stages.findIndex(s => s.id === statusMap[data?.status]);

  return (
    <div className="max-w-3xl mx-auto mt-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Tracking Token</p>
          <h1 className="text-2xl font-bold text-zinc-900 font-mono">{token}</h1>
        </div>
        <div className="text-right">
          <p className="text-xs text-zinc-500 flex items-center justify-end gap-1">
            <RefreshCw className="w-3 h-3" /> Last updated: {lastRefreshed}
          </p>
        </div>
      </div>

      {error && <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
      {/* Pipeline Visualizer */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-6">
        <h2 className="text-sm font-semibold text-zinc-900 mb-8 uppercase tracking-wide">Live Progress</h2>
        
        <div className="relative">
          <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-100 -translate-y-1/2 rounded-full"></div>
          <div 
            className="absolute top-1/2 left-0 h-1 bg-emerald-500 -translate-y-1/2 rounded-full transition-all duration-1000"
            style={{ width: `${(Math.max(0, currentIdx) / (stages.length - 1)) * 100}%` }}
          ></div>
          
          <div className="relative flex justify-between">
            {stages.map((stage, idx) => {
              const isPast = idx < currentIdx;
              const isCurrent = idx === currentIdx;
              
              return (
                <div key={stage.id} className="flex flex-col items-center group">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 transition-colors ${isPast ? 'bg-emerald-500 text-white' : isCurrent ? 'bg-emerald-100 border-2 border-emerald-500 text-emerald-600 animate-pulse' : 'bg-slate-100 border-2 border-slate-200 text-slate-400'}`}>
                    {isPast ? <Check className="w-4 h-4" /> : isCurrent ? <Clock className="w-4 h-4" /> : <div className="w-2 h-2 rounded-full bg-slate-300"></div>}
                  </div>
                  <span className={`text-xs mt-3 font-medium text-center w-20 ${isCurrent ? 'text-emerald-700' : 'text-zinc-500'}`}>
                    {stage.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Details Card */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <div className="flex gap-3 mb-4">
            <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-md border border-indigo-100">{data?.category || 'Under review'}</span>
            <span className="px-2.5 py-1 bg-rose-50 text-rose-700 text-xs font-semibold rounded-md border border-rose-100 uppercase tracking-wide">Severity: {data?.severity || 'Pending'}</span>
          </div>
          <h2 className="text-xl font-bold text-zinc-900">Your civic issue is being processed</h2>
        </div>
        
        {statusMap[data?.status] === 'Routing' && (
          <div className="bg-emerald-50 p-6 border-b border-emerald-100">
            <h3 className="text-sm font-semibold text-emerald-800 mb-2 flex items-center gap-2">
              <CheckCircle className="w-4 h-4" /> Match Found
            </h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-emerald-900 font-bold text-lg">{data?.matched_university || 'University partner'}</p>
                <p className="text-emerald-700 text-sm">Assigned based on civil engineering expertise.</p>
              </div>
              <div className="text-right">
                <span className="text-2xl font-black text-emerald-600 block">Matched</span>
                <span className="text-xs font-medium text-emerald-700 uppercase tracking-wider">Relevance Score</span>
              </div>
            </div>
          </div>
        )}

        <div className="p-6 bg-slate-50">
          <h3 className="text-sm font-semibold text-zinc-900 mb-4">Activity Log</h3>
          <div className="space-y-4">
            <div className="flex gap-4">
              <div className="w-2 h-2 mt-1.5 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.1)]"></div>
              <div>
                <p className="text-sm font-medium text-zinc-900">Routed to IIT Patna</p>
                <p className="text-xs text-zinc-500">Today, 10:24 AM</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="w-2 h-2 mt-1.5 rounded-full bg-slate-300"></div>
              <div>
                <p className="text-sm font-medium text-zinc-900">Approved by Officer (Sub-Divisional Magistrate)</p>
                <p className="text-xs text-zinc-500">Today, 09:15 AM</p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="w-2 h-2 mt-1.5 rounded-full bg-slate-300"></div>
              <div>
                <p className="text-sm font-medium text-zinc-900">Complaint Submitted & Triaged</p>
                <p className="text-xs text-zinc-500">Yesterday, 08:30 PM</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CheckCircle({ className }) {
  return <CheckCircle2 className={className} />;
}
import { CheckCircle2 } from 'lucide-react';
