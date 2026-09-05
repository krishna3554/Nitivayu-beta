import React, { useEffect, useState } from 'react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import { Activity, Database, FileText, IndianRupee, Server, AlertTriangle } from 'lucide-react';
import { getDashboardStats } from '../services/api';

const BAR_COLORS = ['#4f46e5', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#64748b'];

function formatINR(amount) {
  const value = Number(amount) || 0;
  if (value >= 10000000) return `₹${(value / 10000000).toFixed(1)} Cr`;
  if (value >= 100000) return `₹${(value / 100000).toFixed(1)} L`;
  return `₹${value.toLocaleString('en-IN')}`;
}

function toChartData(distribution) {
  return Object.entries(distribution || {}).map(([name, value], index) => ({
    name, value, fill: BAR_COLORS[index % BAR_COLORS.length],
  }));
}

export default function ScalabilityDashboard({ bare = false }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    getDashboardStats()
      .then(({ data }) => setStats(data))
      .catch((err) => setError(err.response?.data?.detail || 'Unable to load dashboard analytics.'))
      .finally(() => setLoading(false));
  }, []);

  const categoryData = toChartData(stats?.category_distribution).sort((a, b) => b.value - a.value);
  const districtData = toChartData(stats?.district_distribution).sort((a, b) => b.value - a.value).slice(0, 8);
  const severityData = toChartData(stats?.severity_distribution).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className={bare ? '' : 'max-w-7xl mx-auto p-6 mt-6'}>
      {!bare && (
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Governance Dashboard</h1>
          <p className="text-zinc-600 text-sm mt-1">Live pipeline metrics across intake, triage, routing and funding.</p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1 text-xs font-bold rounded-full border ${error ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
          <div className={`w-2 h-2 rounded-full ${error ? 'bg-rose-500' : 'bg-emerald-500 animate-pulse'}`}></div>
          {error ? 'DATA UNAVAILABLE' : 'LIVE DATA'}
        </div>
      </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          {[1, 2, 3, 4].map(i => <div key={i} className="bg-white p-5 rounded-xl border border-slate-200 h-32 animate-pulse"><div className="h-4 bg-slate-100 rounded w-1/2 mb-3"></div><div className="h-8 bg-slate-100 rounded w-2/3"></div></div>)}
        </div>
      ) : error ? (
        <div className="mb-8 p-4 bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-xl flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      ) : (
      <>
      {/* KPI Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">Total Submissions</p>
            <FileText className="w-4 h-4 text-primary" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{stats?.total_submissions ?? 0}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">citizen issues reported</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">Triaged Problems</p>
            <Activity className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{stats?.triage_throughput ?? 0}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">{stats?.sla_compliance_percent ?? 0}% routed onward</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">Partner Universities</p>
            <Database className="w-4 h-4 text-sky-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{stats?.active_workers ?? 0}<span className="text-lg font-medium text-zinc-400"> active</span></p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">academic network</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">CSR Pledged</p>
            <IndianRupee className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{formatINR(stats?.total_pledged_inr)}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">corporate funding committed</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Issues by Category</h3>
          <div className="h-64">
            {categoryData.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center pt-24">No categorized issues yet.</p>
            ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryData} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} width={95} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} name="Issues">
                  {categoryData.map(entry => <Cell key={entry.name} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Top Districts</h3>
          <div className="h-64">
            {districtData.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center pt-24">No district data yet.</p>
            ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={districtData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} interval={0} angle={-18} dy={8} height={52} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} name="Issues">
                  {districtData.map(entry => <Cell key={entry.name} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Severity Mix (1–5)</h3>
          <div className="h-64">
            {severityData.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center pt-24">No severity data yet.</p>
            ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={severityData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Bar dataKey="value" radius={[6, 6, 0, 0]} name="Issues" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Pipeline Services</h3>
          <div className="space-y-4">
            {[
              { icon: Server, name: 'FastAPI Backend', sub: `${stats?.total_submissions ?? 0} submissions served` },
              { icon: Database, name: 'PostgreSQL + pgvector', sub: `${stats?.triage_throughput ?? 0} problems triaged` },
              { icon: Activity, name: 'Temporal Workflows', sub: `${stats?.active_workers ?? 0} universities in routing network` },
            ].map(({ icon: Icon, name, sub }) => (
              <div key={name} className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary-subtle text-primary rounded-md"><Icon className="w-5 h-5" /></div>
                  <div>
                    <p className="text-sm font-bold text-zinc-900">{name}</p>
                    <p className="text-xs text-zinc-500">{sub}</p>
                  </div>
                </div>
                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">Live</span>
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
