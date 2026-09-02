import React, { useEffect, useMemo, useState } from 'react';
import { Search, Filter, Check, X, AlertTriangle, ArrowRight } from 'lucide-react';
import { decideComplaint, getQueue } from '../services/api';

export default function OfficerReviewQueue() {
  const [selectedRows, setSelectedRows] = useState(new Set());
  
  const [queue, setQueue] = useState([]);
  const [search, setSearch] = useState('');
  const loadQueue = async () => { try { const { data } = await getQueue(); setQueue(data.map(item => ({ ...item, severity: Number(item.severity) >= 4 ? 'High' : 'Medium', topMatch: item.top_matches?.[0]?.university_name || 'Awaiting match', slaTimer: `${item.sla_hours_remaining}h` }))); } catch (error) { console.error(error); } };
  useEffect(() => { loadQueue(); }, []);
  const visibleQueue = useMemo(() => queue.filter(item => `${item.id} ${item.title} ${item.district}`.toLowerCase().includes(search.toLowerCase())), [queue, search]);
  const decide = async (id, decision) => { try { await decideComplaint(id, { decision }); await loadQueue(); } catch (error) { alert(error.response?.data?.detail || 'Unable to save decision.'); } };

  const toggleRow = (id) => {
    const newSet = new Set(selectedRows);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedRows(newSet);
  };

  const getSeverityBadge = (sev) => {
    const styles = {
      'Critical': 'bg-rose-100 text-rose-700 border-rose-200',
      'High': 'bg-amber-100 text-amber-700 border-amber-200',
      'Medium': 'bg-sky-100 text-sky-700 border-sky-200',
      'Low': 'bg-slate-100 text-slate-700 border-slate-200'
    };
    return <span className={`px-2 py-1 text-xs font-semibold rounded-md border ${styles[sev]}`}>{sev}</span>;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto h-[calc(100vh-64px)] flex flex-col">
      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4 mb-6 shrink-0">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-sm font-medium text-zinc-500">Intake Volume</p>
          <p className="text-2xl font-bold text-zinc-900 mt-1">1,204</p>
          <p className="text-xs text-emerald-600 mt-1">↑ 12% today</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-sm font-medium text-zinc-500">Triage Throughput</p>
          <p className="text-2xl font-bold text-zinc-900 mt-1">845</p>
          <p className="text-xs text-zinc-500 mt-1">per hour</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-sm font-medium text-zinc-500">SLA Compliance</p>
          <p className="text-2xl font-bold text-emerald-600 mt-1">98.2%</p>
          <p className="text-xs text-zinc-500 mt-1">Target: 95%</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-sm font-medium text-zinc-500">Active Workers</p>
          <p className="text-2xl font-bold text-zinc-900 mt-1">42/50</p>
          <p className="text-xs text-emerald-600 mt-1">Healthy</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input 
              type="text" 
              placeholder="Search ID, keyword..." 
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="pl-9 pr-4 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 w-64 outline-none"
            />
          </div>
          <button className="flex items-center gap-2 px-3 py-2 border border-slate-300 rounded-lg text-sm font-medium text-zinc-700 hover:bg-slate-50 transition-colors">
            <Filter className="w-4 h-4" /> Filters
          </button>
        </div>
        
        {selectedRows.size > 0 && (
          <div className="flex items-center gap-3 bg-indigo-50 px-4 py-2 rounded-lg border border-indigo-100">
            <span className="text-sm font-semibold text-indigo-700">{selectedRows.size} selected</span>
            <button className="text-sm font-medium px-3 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700">Bulk Approve</button>
          </div>
        )}
      </div>

      {/* Table Area (Flex-1 for scrolling) */}
      <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
              <tr>
                <th className="p-3 w-12 text-center">
                  <input 
                    type="checkbox" 
                    className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
              onChange={(e) => {
                      if(e.target.checked) setSelectedRows(new Set(visibleQueue.map(q => q.id)));
                      else setSelectedRows(new Set());
                    }}
                    checked={selectedRows.size === visibleQueue.length && visibleQueue.length > 0}
                  />
                </th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider">ID</th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider w-1/3">Issue Summary</th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider">District</th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Severity</th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider">Top Match</th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider">SLA</th>
                <th className="p-3 text-xs font-semibold text-zinc-500 uppercase tracking-wider text-right pr-6">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleQueue.map((row) => (
                <tr key={row.id} className={`hover:bg-slate-50/80 transition-colors ${selectedRows.has(row.id) ? 'bg-indigo-50/30' : ''}`}>
                  <td className="p-3 text-center">
                    <input 
                      type="checkbox" 
                      className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      checked={selectedRows.has(row.id)}
                      onChange={() => toggleRow(row.id)}
                    />
                  </td>
                  <td className="p-3 text-sm font-medium text-zinc-900 font-mono">{row.id}</td>
                  <td className="p-3">
                    <p className="text-sm text-zinc-900 font-medium truncate max-w-sm" title={row.title}>{row.title}</p>
                  </td>
                  <td className="p-3 text-sm text-zinc-600">{row.district}</td>
                  <td className="p-3">{getSeverityBadge(row.severity)}</td>
                  <td className="p-3 text-sm text-emerald-700 font-medium">{row.topMatch}</td>
                  <td className="p-3 text-sm text-zinc-600 flex items-center gap-1">
                    {row.severity === 'Critical' && <AlertTriangle className="w-3 h-3 text-rose-500" />}
                    <span className={row.severity === 'Critical' ? 'text-rose-600 font-semibold' : ''}>{row.slaTimer}</span>
                  </td>
                  <td className="p-3 text-right pr-4">
                    <div className="flex items-center justify-end gap-2">
                      <button className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded border border-transparent hover:border-emerald-200 transition-colors" title="Approve & Route">
                        <Check onClick={() => decide(row.id, 'APPROVE')} className="w-4 h-4" />
                      </button>
                      <button className="p-1.5 text-rose-600 hover:bg-rose-50 rounded border border-transparent hover:border-rose-200 transition-colors" title="Reject">
                        <X onClick={() => decide(row.id, 'REJECT')} className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-sm text-zinc-500">
          <div>Showing 1 to 50 of 12,492 entries</div>
          <div className="flex gap-4">
            <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white border border-slate-300 rounded text-xs font-mono">j</kbd>/<kbd className="px-1.5 py-0.5 bg-white border border-slate-300 rounded text-xs font-mono">k</kbd> navigate</span>
            <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white border border-slate-300 rounded text-xs font-mono">a</kbd> approve</span>
          </div>
        </div>
      </div>
    </div>
  );
}
