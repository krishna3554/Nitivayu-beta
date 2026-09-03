import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Check, Clock, RefreshCw, Search, CheckCircle2 } from 'lucide-react';
import { getComplaint, getErrorMessage } from '../services/api';
import { LoadingState } from './StateView';

const stages = [
  { id: 'Submitted', label: 'Submitted' },
  { id: 'Triaging', label: 'AI Triaging' },
  { id: 'Officer Review', label: 'Officer Review' },
  { id: 'Routing', label: 'Routed to University' },
  { id: 'University Working', label: 'Under Work' },
  { id: 'Completed', label: 'Resolved' }
];

const statusMap = { PENDING_TRIAGE: 'Triaging', TRIAGING: 'Triaging', PENDING_OFFICER_REVIEW: 'Officer Review', ROUTED: 'Routing', ACCEPTED: 'University Working', COMPLETED: 'Completed', REJECTED: 'Completed' };

function formatTimestamp(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

export default function LiveTrackingCard() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [lookupToken, setLookupToken] = useState('');
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const loadStatus = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const response = await getComplaint(token);
      setData(response.data);
      setError('');
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      setData(null);
      setError(getErrorMessage(err, 'We could not find this tracking token.'));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadStatus();
    if (!token) return undefined;
    const timer = setInterval(loadStatus, 30000);
    return () => clearInterval(timer);
  }, [loadStatus, token]);

  if (!token) {
    return (
      <div className="max-w-md mx-auto mt-16 p-6 bg-white rounded-xl shadow-sm border border-slate-200">
        <h1 className="text-2xl font-bold text-zinc-900 mb-2">Track your issue</h1>
        <p className="text-sm text-zinc-600 mb-6">Enter the tracking token you received after submitting your report.</p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const trimmed = lookupToken.trim();
            if (trimmed) navigate(`/track/${encodeURIComponent(trimmed)}`);
          }}
          className="space-y-4"
        >
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
            <input
              type="text"
              required
              value={lookupToken}
              onChange={(event) => setLookupToken(event.target.value)}
              placeholder="NITIVAYU-2026-JH-XXXXXX"
              className="w-full pl-10 pr-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none font-mono text-sm"
            />
          </div>
          <button type="submit" className="w-full py-3 bg-zinc-900 text-white rounded-lg font-medium hover:bg-zinc-800 transition-colors">
            Track Issue
          </button>
        </form>
      </div>
    );
  }

  const currentIdx = stages.findIndex(s => s.id === statusMap[data?.status]);
  const activity = data?.activity?.length ? data.activity : [
    { action: 'SUBMITTED', actor_role: 'citizen', timestamp: data?.submitted_at },
  ];

  return (
    <div className="max-w-3xl mx-auto mt-8 px-4 pb-12">
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm font-medium text-zinc-500 uppercase tracking-wider">Tracking Token</p>
          <h1 className="text-2xl font-bold text-zinc-900 font-mono">{token}</h1>
        </div>
        <div className="text-right">
          {lastRefreshed && (
            <p className="text-xs text-zinc-500 flex items-center justify-end gap-1">
              <RefreshCw className="w-3 h-3" /> Last updated: {lastRefreshed}
            </p>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadStatus} className="text-xs font-semibold text-rose-700 underline">Retry</button>
        </div>
      )}

      {loading && !data && <LoadingState label="Fetching live status…" />}

      {data && (
        <>
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
              <div className="flex flex-wrap gap-3 mb-4">
                <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded-md border border-indigo-100">{data.category || 'Under review'}</span>
                <span className="px-2.5 py-1 bg-rose-50 text-rose-700 text-xs font-semibold rounded-md border border-rose-100 uppercase tracking-wide">Severity: {data.severity || 'Pending'}</span>
                {data.district && <span className="px-2.5 py-1 bg-slate-100 text-zinc-700 text-xs font-semibold rounded-md border border-slate-200">{data.district}</span>}
              </div>
              <h2 className="text-xl font-bold text-zinc-900">{data.title || 'Your civic issue is being processed'}</h2>
            </div>

            {data.matched_university && (
              <div className="bg-emerald-50 p-6 border-b border-emerald-100">
                <h3 className="text-sm font-semibold text-emerald-800 mb-2 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" /> Match Found
                </h3>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-emerald-900 font-bold text-lg">{data.matched_university}</p>
                    <p className="text-emerald-700 text-sm">Assigned based on department expertise and capacity.</p>
                  </div>
                  <div className="text-right">
                    <span className="text-2xl font-black text-emerald-600 block">Matched</span>
                    <span className="text-xs font-medium text-emerald-700 uppercase tracking-wider">Relevance Score</span>
                  </div>
                </div>
              </div>
            )}

            {data.milestones?.length > 0 && (
              <div className="p-6 border-b border-slate-100">
                <h3 className="text-sm font-semibold text-zinc-900 mb-4">Project Milestones</h3>
                <div className="space-y-3">
                  {data.milestones.map((milestone) => (
                    <div key={milestone.milestone_id} className="flex items-center justify-between text-sm">
                      <span className="text-zinc-700 font-medium">{milestone.title}</span>
                      <span className={`px-2 py-0.5 text-xs font-semibold rounded-md border ${milestone.status === 'VERIFIED' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : milestone.status === 'SUBMITTED' ? 'bg-sky-50 text-sky-700 border-sky-100' : 'bg-slate-100 text-zinc-600 border-slate-200'}`}>
                        {milestone.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="p-6 bg-slate-50">
              <h3 className="text-sm font-semibold text-zinc-900 mb-4">Activity Log</h3>
              <div className="space-y-4">
                {activity.map((event, idx) => (
                  <div key={`${event.action}-${idx}`} className="flex gap-4">
                    <div className={`w-2 h-2 mt-1.5 rounded-full ${idx === 0 ? 'bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.1)]' : 'bg-slate-300'}`}></div>
                    <div>
                      <p className="text-sm font-medium text-zinc-900">{event.action.replaceAll('_', ' ')}</p>
                      <p className="text-xs text-zinc-500">{formatTimestamp(event.timestamp)}{event.actor_role ? ` · by ${event.actor_role}` : ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
