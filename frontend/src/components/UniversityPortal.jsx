import React, { useCallback, useEffect, useState } from 'react';
import { Users, FileText, CheckCircle2, UploadCloud } from 'lucide-react';
import { getErrorMessage, getUniversityInbox, getUniversityProjects, getUniversityWorkspace, respondToAssignment } from '../services/api';
import { EmptyState, ErrorState, LoadingState } from './StateView';

export default function UniversityPortal() {
  const [activeTab, setActiveTab] = useState('inbox');
  const [workspace, setWorkspace] = useState(null);
  const [inbox, setInbox] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [workspaceRes, inboxRes, projectsRes] = await Promise.all([
        getUniversityWorkspace(),
        getUniversityInbox(),
        getUniversityProjects(),
      ]);
      setWorkspace(workspaceRes.data);
      setInbox(inboxRes.data);
      setProjects(projectsRes.data);
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to load the university workspace.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const respond = async (id, response) => {
    setActionError('');
    try {
      await respondToAssignment(id, { response });
      await loadAll();
    } catch (err) {
      setActionError(getErrorMessage(err, 'Unable to submit your response.'));
    }
  };

  if (loading) {
    return <div className="max-w-6xl mx-auto p-6 mt-6"><LoadingState label="Loading university workspace…" /></div>;
  }
  if (error) {
    return <div className="max-w-6xl mx-auto p-6 mt-6"><ErrorState message={error} onRetry={loadAll} /></div>;
  }

  return (
    <div className="max-w-6xl mx-auto p-6 mt-6 flex flex-col md:flex-row gap-8">
      {/* Sidebar Navigation */}
      <div className="md:w-64 shrink-0">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 md:sticky md:top-24">
          <div className="mb-6 px-2">
            <h2 className="text-sm font-bold text-zinc-900 uppercase tracking-wider">{workspace?.name || 'University Workspace'}</h2>
            <p className="text-xs text-zinc-500 mt-1">{(workspace?.domain_specializations || []).slice(0, 2).join(' · ') || 'IIC Nodal Cell'}</p>
            {workspace && (
              <p className="text-xs text-zinc-500 mt-2">Load: <span className="font-semibold text-zinc-700">{workspace.current_load}/{workspace.active_capacity}</span> active challenges</p>
            )}
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
      <div className="flex-1 min-w-0">
        {actionError && <p role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{actionError}</p>}

        {activeTab === 'inbox' && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-zinc-900 mb-6">Assigned Challenges</h2>
            {inbox.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
                <EmptyState title="No pending offers" message="When officers route a challenge to your institution, it will appear here for acceptance." />
              </div>
            ) : inbox.map(item => (
              <div key={item.assignment_id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className="px-2 py-1 bg-indigo-50 text-indigo-700 text-xs font-semibold rounded border border-indigo-100">{item.category}</span>
                    {item.district && <span className="px-2 py-1 bg-slate-100 text-zinc-700 text-xs font-semibold rounded">{item.district}</span>}
                    {item.severity >= 4 && <span className="px-2 py-1 bg-rose-50 text-rose-700 text-xs font-semibold rounded border border-rose-100">Severity {item.severity}/5</span>}
                  </div>
                  <h3 className="text-lg font-bold text-zinc-900">{item.problem_title}</h3>
                  <p className="text-sm text-zinc-500 mt-1 line-clamp-2">{item.summary}</p>
                </div>

                <div className="flex flex-row md:flex-col items-center md:items-end justify-between gap-3 shrink-0">
                  <div className="text-right">
                    <span className="text-2xl font-black text-emerald-600">{Math.round((item.match_score || 0) * 100)}%</span>
                    <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Match Score</p>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => respond(item.assignment_id, 'ACCEPT')} className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors">Accept</button>
                    <button onClick={() => respond(item.assignment_id, 'DECLINE')} className="px-4 py-2 text-sm font-medium border border-slate-300 text-zinc-700 rounded-lg hover:bg-slate-50 transition-colors">Decline</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'projects' && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-zinc-900 mb-6">Active Projects</h2>
            {projects.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
                <EmptyState title="No active projects yet" message="Accept a challenge from the inbox to form a project team and track milestones here." />
              </div>
            ) : projects.map(item => (
              <div key={item.team_id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                <div className="flex flex-col md:flex-row justify-between md:items-start gap-3 mb-8">
                  <div>
                    <h3 className="text-xl font-bold text-zinc-900">{item.title}</h3>
                    <p className="text-sm text-zinc-500 mt-1 flex items-center gap-2">
                      <Users className="w-4 h-4" /> {item.faculty_mentor_name} · Lead: {item.student_lead_name}
                    </p>
                  </div>
                  <span className="self-start px-3 py-1 bg-indigo-50 text-indigo-700 text-xs font-bold rounded-full uppercase tracking-wider">
                    Milestone {item.current_milestone}/3
                  </span>
                </div>

                {/* Milestone Tracker */}
                <div className="relative mb-8">
                  <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-100 -translate-y-1/2"></div>
                  <div className="absolute top-1/2 left-0 h-1 bg-indigo-500 -translate-y-1/2 transition-all" style={{ width: `${(Math.max(0, item.current_milestone - 1) / 2) * 100}%` }}></div>

                  <div className="relative flex justify-between">
                    {(item.milestones.length ? item.milestones : []).map((milestone, idx) => {
                      const isDone = milestone.status === 'VERIFIED';
                      const isCurrent = !isDone && (idx === 0 || item.milestones[idx - 1]?.status === 'VERIFIED');
                      return (
                        <div key={milestone.milestone_id} className="flex flex-col items-center group">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center z-10 ${isDone ? 'bg-indigo-600 text-white' : isCurrent ? 'bg-indigo-100 border-2 border-indigo-600 text-indigo-600' : 'bg-slate-100 text-slate-400'}`}>
                            {isDone ? <CheckCircle2 className="w-5 h-5" /> : <span className="text-sm font-bold">{milestone.milestone_num}</span>}
                          </div>
                          <span className={`text-xs mt-2 font-medium text-center w-24 ${isCurrent ? 'text-indigo-700' : 'text-zinc-500'}`}>{milestone.title}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
                  <h4 className="text-sm font-semibold text-zinc-900 mb-3 flex items-center gap-2">
                    <FileText className="w-4 h-4" /> Submit current milestone evidence
                  </h4>
                  <div className="flex flex-col sm:flex-row gap-4">
                    <div className="flex-1 border-2 border-dashed border-slate-300 rounded-lg p-4 text-center hover:bg-slate-100 transition-colors cursor-pointer bg-white">
                      <UploadCloud className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                      <p className="text-xs text-zinc-600">Upload CAD/Design PDF</p>
                    </div>
                    <button className="px-6 py-2 bg-zinc-900 text-white rounded-lg text-sm font-medium hover:bg-zinc-800 sm:self-end transition-colors">
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
