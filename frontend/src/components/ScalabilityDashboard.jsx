import React, { useCallback, useEffect, useState } from 'react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from 'recharts';
import { Activity, Database, IndianRupee, FileText } from 'lucide-react';
import { getDashboardStats, getErrorMessage } from '../services/api';
import { ErrorState, LoadingState } from './StateView';

const CHART_COLORS = ['#4F46E5', '#059669', '#0284C7', '#F59E0B', '#E11D48', '#7C3AED', '#0D9488', '#B45309', '#475569', '#DB2777'];

function formatINR(amount) {
  const value = Number(amount || 0);
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(1)} Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(1)} L`;
  return `₹${value.toLocaleString('en-IN')}`;
}

export default function ScalabilityDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await getDashboardStats();
      setStats(data);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to load platform analytics.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  if (loading) {
    return <div className="max-w-7xl mx-auto p-6 mt-6"><LoadingState label="Loading analytics…" /></div>;
  }
  if (error) {
    return <div className="max-w-7xl mx-auto p-6 mt-6"><ErrorState message={error} onRetry={loadStats} /></div>;
  }

  const categoryData = Object.entries(stats?.category_distribution || {}).map(([name, count]) => ({ name, count }));
  const districtData = Object.entries(stats?.district_distribution || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, count]) => ({ name, count }));

  return (
    <div className="max-w-7xl mx-auto p-6 mt-6">
      <div className="flex flex-col md:flex-row justify-between md:items-end gap-3 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Platform Overview</h1>
          <p className="text-zinc-600 text-sm mt-1">Live pipeline metrics across intake, triage, routing, and funding.</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-full border border-emerald-200 self-start">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          LIVE DATA
        </div>
      </div>

      {/* KPI Gauges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">Total Submissions</p>
            <FileText className="w-4 h-4 text-indigo-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{stats?.total_submissions ?? 0}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">citizen reports received</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">Problems Triaged</p>
            <Activity className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{stats?.total_problems ?? 0}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">{stats?.sla_compliance_percent ?? 0}% routed onward</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">University Network</p>
            <Database className="w-4 h-4 text-sky-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{stats?.active_workers ?? 0}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">partner institutions</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">CSR Funds Pledged</p>
            <IndianRupee className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">{formatINR(stats?.total_pledged_inr)}</p>
          <p className="text-xs text-zinc-500 mt-2 font-medium">committed to projects</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Problems by Category</h3>
          <div className="h-64">
            {categoryData.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center pt-24">No triaged problems yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} dy={10} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Bar dataKey="count" fill="#4F46E5" radius={[6, 6, 0, 0]} name="Problems" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Reports by District</h3>
          <div className="h-64">
            {districtData.length === 0 ? (
              <p className="text-sm text-zinc-500 text-center pt-24">No district data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={districtData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={80} innerRadius={45} paddingAngle={2}>
                    {districtData.map((entry, idx) => (
                      <Cell key={entry.name} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
