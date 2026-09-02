import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
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
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('nitivayu_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const submitComplaint = (data) => api.post('/submissions', data, { headers: { 'Content-Type': 'multipart/form-data' } });
export const getComplaint = (token) => api.get(`/submissions/${token}/track`);
export const getQueue = (params) => api.get('/officer/review-queue', { params });
export const decideComplaint = (id, data) => api.post(`/officer/reviews/${id}/decision`, data);
export const getBatchStatus = () => api.get('/admin/triage/schedules');
export const runBatch = (data) => api.post('/admin/triage/trigger-batch', data);
export const getUniversityInbox = () => api.get('/university/inbox');
export const respondToAssignment = (id, data) => api.post(`/university/assignments/${id}/respond`, data);
export const getCSRChallenges = () => api.get('/industry/opportunities');
export const createCsrPledge = (data) => api.post('/industry/pledges', data);
export const getDashboardStats = () => api.get('/analytics/overview');
export const loginUser = (credentials) => api.post('/auth/login', credentials);

export default api;
