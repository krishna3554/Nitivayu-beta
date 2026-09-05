import React, { useState } from 'react';
import { Play, Settings, Calendar, Clock, Download, CheckCircle, AlertCircle } from 'lucide-react';
import { getBatchStatus, getErrorMessage, runBatch } from '../services/api';

export default function BatchTriageControl() {
  const [isRunning, setIsRunning] = useState(false);
  const [schedule, setSchedule] = useState(null);
  const [message, setMessage] = useState('');
  const [loadError, setLoadError] = useState('');
  React.useEffect(() => { getBatchStatus().then(({ data }) => setSchedule(data)).catch((err) => setLoadError(getErrorMessage(err, 'Unable to load batch schedule.'))); }, []);
  
  const history = [
    { id: 'B-004', date: '2023-11-24 02:00', mode: 'Daily', count: 1240, status: 'Success', time: '14m 22s' },
    { id: 'B-003', date: '2023-11-23 02:00', mode: 'Daily', count: 1105, status: 'Success', time: '12m 45s' },
    { id: 'B-002', date: '2023-11-22 02:00', mode: 'Daily', count: 980, status: 'Warning', time: '18m 10s' },
  ];

  const handleRun = async () => {
    if(window.confirm('Are you sure you want to trigger a manual batch run?')) {
      setIsRunning(true);
      try { const { data } = await runBatch({ cadence_type: schedule?.active_cadence || 'weekly', include_unassigned_only: true }); setMessage(`Batch ${data.batch_workflow_id} is queued.`); } catch (error) { setMessage(getErrorMessage(error, 'Unable to start batch.')); }
      finally { setIsRunning(false); }
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6 mt-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900">Batch Triage Control</h1>
        <p className="text-zinc-600 mt-1">Manage the AI background processor for high-volume complaint routing.</p>
      </div>

      {loadError && <p role="alert" className="mb-5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{loadError}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="col-span-2 bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-zinc-900 flex items-center gap-2">
              <Settings className="w-5 h-5 text-primary" /> Current Configuration
            </h2>
            <span className="px-3 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded-full uppercase tracking-wider flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> Active
            </span>
          </div>

          <div className="grid grid-cols-2 gap-8">
            <div>
              <p className="text-sm font-medium text-zinc-500 mb-1">Schedule Mode</p>
              <select className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary text-sm font-medium text-zinc-900">
                <option value="continuous">Continuous (Queue-based)</option>
                <option value="daily">Daily Cron (2:00 AM)</option>
                <option value="weekly">Weekly Cron</option>
              </select>
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-500 mb-1">Unprocessed Backlog</p>
              <p className="text-3xl font-black text-zinc-900">3,492 <span className="text-sm font-medium text-zinc-500 font-normal">items</span></p>
            </div>
          </div>
        </div>
      {message && <p className="mb-5 text-sm text-primary">{message}</p>}

        <div className="card flex flex-col justify-center p-6">
          <h3 className="type-label-sm mb-4 text-zinc-500">Manual override</h3>
          <button 
            onClick={handleRun}
            disabled={isRunning}
            className="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-60"
          >
            {isRunning ? (
              <><div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Running batch…</>
            ) : (
              <><Play className="w-5 h-5" /> Run batch now</>
            )}
          </button>
          <p className="type-body-sm mt-3 text-center text-zinc-400">Spawns a Temporal workflow immediately</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-zinc-900">Run History</h2>
          <span className="text-xs text-zinc-400 font-medium">Sample history</span>
        </div>
        <table className="w-full text-left">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Run ID</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Date & Time</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Items Processed</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Duration</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Status</th>
              <th className="p-4 text-xs font-semibold text-zinc-500 uppercase tracking-wider text-right">Report</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {history.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50 transition-colors">
                <td className="p-4 text-sm font-medium text-zinc-900 font-mono">{row.id}</td>
                <td className="p-4 text-sm text-zinc-600 flex items-center gap-2"><Calendar className="w-4 h-4 text-zinc-400" /> {row.date}</td>
                <td className="p-4 text-sm font-medium text-zinc-900">{row.count.toLocaleString()}</td>
                <td className="p-4 text-sm text-zinc-600 flex items-center gap-1"><Clock className="w-3 h-3 text-zinc-400" /> {row.time}</td>
                <td className="p-4">
                  {row.status === 'Success' ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-md border border-emerald-100">
                      <CheckCircle className="w-3 h-3" /> {row.status}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-50 text-amber-700 text-xs font-semibold rounded-md border border-amber-100">
                      <AlertCircle className="w-3 h-3" /> {row.status}
                    </span>
                  )}
                </td>
                <td className="p-4 text-right">
                    <button className="p-2 text-zinc-400 hover:text-primary transition-colors" title="Download CSV">
                    <Download className="w-4 h-4 inline" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
