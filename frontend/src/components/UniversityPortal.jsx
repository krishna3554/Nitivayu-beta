import React, { useState } from 'react';
import { Users, FileText, CheckCircle2, ChevronRight, UploadCloud } from 'lucide-react';

export default function UniversityPortal() {
  const [activeTab, setActiveTab] = useState('inbox');

  const inbox = [
    { id: 'C-1002', title: 'Severe waterlogging in main market', score: 0.94, district: 'Patna' },
    { id: 'C-1005', title: 'Bridge structural crack on highway 32', score: 0.98, district: 'Gaya' },
  ];

  const projects = [
    { id: 'P-042', title: 'Sadar Market Drainage Redesign', milestone: 1, team: 'Civil Eng Dept (Prof. Sharma)' }
  ];

  return (
    <div className="max-w-6xl mx-auto p-6 mt-6 flex gap-8">
      {/* Sidebar Navigation */}
      <div className="w-64 shrink-0">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 sticky top-24">
          <div className="mb-6 px-2">
            <h2 className="text-sm font-bold text-zinc-900 uppercase tracking-wider">IIT Patna Workspace</h2>
            <p className="text-xs text-zinc-500 mt-1">Civil & Structural Eng.</p>
          </div>
          <nav className="space-y-1">
            <button 
              onClick={() => setActiveTab('inbox')}
              className={`w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'inbox' ? 'bg-indigo-50 text-indigo-700' : 'text-zinc-600 hover:bg-slate-50'}`}
            >
              <span>Challenge Inbox</span>
              {inbox.length > 0 && <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs rounded-full">{inbox.length}</span>}
            </button>
            <button 
              onClick={() => setActiveTab('projects')}
              className={`w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === 'projects' ? 'bg-indigo-50 text-indigo-700' : 'text-zinc-600 hover:bg-slate-50'}`}
            >
              <span>Active Projects</span>
              <span className="px-2 py-0.5 bg-slate-100 text-zinc-600 text-xs rounded-full">{projects.length}</span>
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1">
        {activeTab === 'inbox' && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-zinc-900 mb-6">Assigned Challenges</h2>
            {inbox.map(item => (
              <div key={item.id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <div className="flex gap-2 mb-2">
                    <span className="px-2 py-1 bg-slate-100 text-zinc-700 text-xs font-semibold rounded font-mono">{item.id}</span>
                    <span className="px-2 py-1 bg-slate-100 text-zinc-700 text-xs font-semibold rounded">{item.district}</span>
                  </div>
                  <h3 className="text-lg font-bold text-zinc-900">{item.title}</h3>
                  <p className="text-sm text-zinc-500 mt-1">Matched based on department expertise profile.</p>
                </div>
                
                <div className="flex flex-col items-end gap-3 shrink-0">
                  <div className="text-right">
                    <span className="text-2xl font-black text-emerald-600">{Math.round(item.score * 100)}%</span>
                    <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Match Score</p>
                  </div>
                  <div className="flex gap-2">
                    <button className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors">Accept</button>
                    <button className="px-4 py-2 text-sm font-medium border border-slate-300 text-zinc-700 rounded-lg hover:bg-slate-50 transition-colors">Decline</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'projects' && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-zinc-900 mb-6">Active Projects</h2>
            {projects.map(item => (
              <div key={item.id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <div className="flex justify-between items-start mb-8">
                  <div>
                    <h3 className="text-xl font-bold text-zinc-900">{item.title}</h3>
                    <p className="text-sm text-zinc-500 mt-1 flex items-center gap-2">
                      <Users className="w-4 h-4" /> {item.team}
                    </p>
                  </div>
                  <span className="px-3 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-full uppercase tracking-wider">
                    Milestone {item.milestone}/3
                  </span>
                </div>

                {/* Milestone Tracker */}
                <div className="relative mb-8">
                  <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-100 -translate-y-1/2"></div>
                  <div className="absolute top-1/2 left-0 w-1/2 h-1 bg-indigo-500 -translate-y-1/2"></div>
                  
                  <div className="relative flex justify-between">
                    {['Feasibility Study', 'Prototype Design', 'Field Validation'].map((label, idx) => {
                      const isPast = idx < item.milestone;
                      const isCurrent = idx === item.milestone;
                      return (
                        <div key={label} className="flex flex-col items-center group">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 ${isPast ? 'bg-indigo-600 text-white' : isCurrent ? 'bg-indigo-100 border-2 border-indigo-600 text-indigo-600' : 'bg-slate-100 text-slate-400'}`}>
                            {isPast ? <CheckCircle2 className="w-5 h-5" /> : <span className="text-sm font-bold">{idx + 1}</span>}
                          </div>
                          <span className={`text-xs mt-2 font-medium ${isCurrent ? 'text-indigo-700' : 'text-zinc-500'}`}>{label}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>

                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
                  <h4 className="text-sm font-semibold text-zinc-900 mb-3 flex items-center gap-2">
                    <FileText className="w-4 h-4" /> Submit Milestone 2: Prototype Design
                  </h4>
                  <div className="flex gap-4">
                    <div className="flex-1 border-2 border-dashed border-slate-300 rounded-lg p-4 text-center hover:bg-slate-100 transition-colors cursor-pointer bg-white">
                      <UploadCloud className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                      <p className="text-xs text-zinc-600">Upload CAD/Design PDF</p>
                    </div>
                    <button className="px-6 py-2 bg-zinc-900 text-white rounded-lg text-sm font-medium hover:bg-zinc-800 self-end transition-colors">
                      Submit for Review
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
