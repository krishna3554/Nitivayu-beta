import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Activity, Database, Cpu, Zap, Server } from 'lucide-react';

export default function ScalabilityDashboard() {
  const throughputData = [
    { time: '10:00', processed: 400, received: 450 },
    { time: '10:05', processed: 300, received: 320 },
    { time: '10:10', processed: 550, received: 500 },
    { time: '10:15', processed: 480, received: 510 },
    { time: '10:20', processed: 600, received: 580 },
    { time: '10:25', processed: 720, received: 700 },
  ];

  return (
    <div className="max-w-7xl mx-auto p-6 mt-6">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">System Telemetry</h1>
          <p className="text-zinc-600 text-sm mt-1">Real-time performance metrics and cluster health.</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-full border border-emerald-200">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          SYSTEM HEALTHY
        </div>
      </div>

      {/* Real-time Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">Temporal Workers</p>
            <Activity className="w-4 h-4 text-indigo-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">42<span className="text-lg font-medium text-zinc-400">/50</span></p>
          <div className="w-full h-1.5 bg-slate-100 rounded-full mt-3 overflow-hidden">
            <div className="h-full bg-indigo-500 rounded-full" style={{ width: '84%' }}></div>
          </div>
        </div>
        
        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">OpenRouter API</p>
            <Zap className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">124<span className="text-lg font-medium text-zinc-400"> req/s</span></p>
          <p className="text-xs text-amber-600 mt-2 font-medium">Latency: ~210ms</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">MiniLM CPU Inference</p>
            <Cpu className="w-4 h-4 text-rose-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">45<span className="text-lg font-medium text-zinc-400"> ms</span></p>
          <p className="text-xs text-emerald-600 mt-2 font-medium">Optimal range</p>
        </div>

        <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
          <div className="flex justify-between items-start mb-2">
            <p className="text-sm font-medium text-zinc-500">pgvector Latency</p>
            <Database className="w-4 h-4 text-sky-500" />
          </div>
          <p className="text-3xl font-black text-zinc-900">12<span className="text-lg font-medium text-zinc-400"> ms</span></p>
          <p className="text-xs text-emerald-600 mt-2 font-medium">Index Hit Rate: 99.4%</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Queue Throughput (last 30m)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={throughputData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Line type="monotone" dataKey="processed" stroke="#10b981" strokeWidth={3} dot={false} name="Processed" />
                <Line type="monotone" dataKey="received" stroke="#cbd5e1" strokeWidth={2} dot={false} name="Received" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h3 className="text-sm font-bold text-zinc-900 mb-6 uppercase tracking-wider">Infrastructure Services</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-100 text-indigo-700 rounded-md"><Server className="w-5 h-5" /></div>
                <div>
                  <p className="text-sm font-bold text-zinc-900">FastAPI Backend Nodes</p>
                  <p className="text-xs text-zinc-500">3 instances active</p>
                </div>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">Healthy</span>
            </div>
            
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-100 text-indigo-700 rounded-md"><Database className="w-5 h-5" /></div>
                <div>
                  <p className="text-sm font-bold text-zinc-900">PostgreSQL 16 Cluster</p>
                  <p className="text-xs text-zinc-500">Primary + 1 Replica</p>
                </div>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">Healthy</span>
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-100 text-indigo-700 rounded-md"><Activity className="w-5 h-5" /></div>
                <div>
                  <p className="text-sm font-bold text-zinc-900">Temporal Cluster</p>
                  <p className="text-xs text-zinc-500">Workflow orchestration</p>
                </div>
              </div>
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 text-xs font-bold rounded">Healthy</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
