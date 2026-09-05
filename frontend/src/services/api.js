import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('nitivayu_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.startsWith('/login')) {
      localStorage.removeItem('nitivayu_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export function getErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (error.code === 'ECONNABORTED') return 'The request timed out. Please try again.';
  if (!error.response) return 'Cannot reach the server. Please check your connection.';
  const detail = error.response.data?.detail;
  if (typeof detail === 'string') return detail;
  if (error.response.status === 403) return 'You do not have permission to perform this action.';
  if (error.response.status === 404) return 'The requested record was not found.';
  if (error.response.status === 429) return 'Too many requests. Please wait a moment and retry.';
  if (error.response.status >= 500) return 'The server encountered an error. Please try again later.';
  return fallback;
}

export const submitComplaint = (data) => api.post('/submissions', data, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000 });
export const getComplaint = (token) => api.get(`/submissions/${token}/track`);
export const getQueue = (params) => api.get('/officer/review-queue', { params });
export const decideComplaint = (id, data) => api.post(`/officer/reviews/${id}/decision`, data);
export const getBatchStatus = () => api.get('/admin/triage/schedules');
export const runBatch = (data) => api.post('/admin/triage/trigger-batch', data);
export const getUniversityWorkspace = () => api.get('/university/workspace');
export const getUniversityInbox = () => api.get('/university/inbox');
export const getUniversityProjects = () => api.get('/university/projects');
export const getUniversityWorkspace = () => api.get('/university/workspace');
export const respondToAssignment = (id, data) => api.post(`/university/assignments/${id}/respond`, data);
export const getCSRChallenges = () => api.get('/industry/opportunities');
export const getCSRPledges = () => api.get('/industry/pledges');
export const createCsrPledge = (data) => api.post('/industry/pledges', data);
export const getCSRPledges = () => api.get('/industry/pledges');
export const getDashboardStats = () => api.get('/analytics/overview');
export const loginUser = (credentials) => api.post('/auth/login', credentials);
export const exportTriageReport = () => api.post('/admin/reports/triage');

export default api;
