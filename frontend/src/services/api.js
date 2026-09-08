import axios from 'axios';

function safeGet(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function safeRemove(...keys) {
  try { keys.forEach((k) => localStorage.removeItem(k)); } catch { /* private mode */ }
}

// VITE_API_URL override (B3): absolute API origin for remote deploys, e.g.
// VITE_API_URL=http://api.example.com/api/v1. Defaults to same-origin /api/v1
// so the nginx proxy (compose) and the Vite dev proxy keep working.
const baseURL = (import.meta.env?.VITE_API_URL || '/api/v1').replace(/\/$/, '');
const defaultTimeout = Number(import.meta.env?.VITE_API_TIMEOUT_MS || 20000) || 20000;

const api = axios.create({
  baseURL,
  // Fail loudly instead of hanging forever: every consumer resolves to
  // content, skeleton, or an error-with-retry — never a permanent spinner.
  // Per-request `timeout` overrides still apply (uploads use 60s below).
  timeout: defaultTimeout,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const sessionRaw = safeGet('nitivayu_session');
  let token = safeGet('nitivayu_token');
  if (!token && sessionRaw) {
    try { token = JSON.parse(sessionRaw)?.token || null; } catch { token = null; }
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const url = error.config?.url || '';
      const hadAuth = Boolean(error.config?.headers?.Authorization);
      const isAuthRoute = url.includes('/auth/');
      // Scope the logout redirect (B2.14): only auth-gated calls log out.
      // Public calls (tracker, opportunities) surface their own error UI.
      // Never redirect when already on /login (loop guard).
      if ((hadAuth || isAuthRoute) && !window.location.pathname.startsWith('/login')) {
        safeRemove('nitivayu_token', 'nitivayu_session');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// FormData MUST NOT go through the default JSON transform: axios 1.x runs
// formToJSON() on FormData whenever Content-Type is application/json, which
// silently turns uploads into a JSON body the backend (correctly) rejects
// with "missing raw_text". Deleting the header per-request lets the browser
// set multipart/form-data with its own boundary. Never set a manual
// multipart Content-Type here either — a boundary-less value breaks parsing.
const formPostConfig = {
  timeout: 60000,
  transformRequest: [(data, headers) => {
    if (headers && typeof headers.delete === 'function') headers.delete('Content-Type');
    else if (headers) delete headers['Content-Type'];
    return data;
  }],
};

export const submitComplaint = (data) => api.post('/submissions', data, formPostConfig);
export const getComplaint = (token) => api.get(`/submissions/${token}/track`);
export const getQueue = (params) => api.get('/officer/review-queue', { params });
export const decideComplaint = (id, data) => api.post(`/officer/reviews/${id}/decision`, data);
export const getProblemDetail = (id) => api.get(`/officer/problems/${id}`);
export const getOfficerUniversities = () => api.get('/officer/universities');
export const getProblemUpdates = (id) => api.get(`/officer/problems/${id}/updates`);
export const getAssignmentDetail = (id) => api.get(`/university/assignments/${id}`);
export const getTeamUpdates = (teamId) => api.get(`/university/teams/${teamId}/updates`);
export const postTeamUpdate = (teamId, data) => api.post(`/university/teams/${teamId}/updates`, data, formPostConfig);
export const getMediaBlob = (assetId) => api.get(`/media/${assetId}`, { responseType: 'blob' });
export const getBatchStatus = () => api.get('/admin/triage/schedules');
export const runBatch = (data) => api.post('/admin/triage/trigger-batch', data);
export const updateBatchSchedule = (data) => api.put('/admin/triage/schedules', data);
export const getBatchHistory = () => api.get('/admin/triage/batch-jobs');
export const getUniversityInbox = () => api.get('/university/inbox');
export const getUniversityProjects = () => api.get('/university/projects');
export const getUniversityWorkspace = () => api.get('/university/workspace');
export const respondToAssignment = (id, data) => api.post(`/university/assignments/${id}/respond`, data);
export const getCSRChallenges = () => api.get('/industry/opportunities');
export const createCsrPledge = (data) => api.post('/industry/pledges', data);
export const getCSRPledges = () => api.get('/industry/pledges');
export const getDashboardStats = () => api.get('/analytics/overview');
export const loginUser = (credentials) => api.post('/auth/login', credentials);
export const exportTriageReport = () => api.post('/admin/reports/triage');

// --- plan4: account-scoped citizen + profile ---
export const getMyReports = () => api.get('/citizen/reports');
export const claimReport = (tracking_token) => api.post('/citizen/reports/claim', { tracking_token });
export const getMe = () => api.get('/auth/me');
export const updateMe = (data) => api.patch('/auth/me', data);

// --- plan4: shared pipeline config (SLA windows, weights, districts) ---
export const getMetaConfig = () => api.get('/meta/config');
export const getDemoAccounts = () => api.get('/meta/demo-accounts');
export const getPublicStats = () => api.get('/meta/public-stats');
export const getPartners = () => api.get('/meta/partners');
export const getFeaturedCases = () => api.get('/meta/featured-cases');

// --- plan4: officer escalations + milestone verification + media review ---
export const getEscalations = () => api.get('/officer/escalations');
export const verifyMilestone = (id, data) => api.post(`/officer/milestones/${id}/verify`, data);
export const clearFlaggedMedia = (assetId) => api.post(`/officer/media/${assetId}/clear`);

// --- plan4: university milestone evidence + team details ---
export const submitMilestone = (id, data) => api.post(`/university/milestones/${id}/submit`, data, formPostConfig);
export const updateTeam = (teamId, data) => api.patch(`/university/teams/${teamId}`, data);

// --- plan4: admin invites list + compliance exports + service health ---
export const getInvites = () => api.get('/admin/invites');
export const revokeInvite = (inviteId) => api.post(`/admin/invites/${inviteId}/revoke`);
export const exportAdmin = (kind) => api.post(`/admin/exports/${kind}`);
export const getServiceHealth = () => api.get('/admin/health/services');

// --- plan4: industry impact + monthly matrix ---
export const getIndustryImpact = () => api.get('/industry/impact');
export const exportMonthlyMatrix = () => api.post('/industry/exports/monthly-matrix');

export default api;
