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

export const submitComplaint = (data) => api.post('/complaints', data);
export const getComplaint = (token) => api.get(`/complaints/${token}`);
export const getQueue = (params) => api.get('/officer/queue', { params });
export const approveComplaint = (id, data) => api.post(`/officer/complaints/${id}/approve`, data);
export const rejectComplaint = (id, data) => api.post(`/officer/complaints/${id}/reject`, data);
export const getBatchStatus = () => api.get('/officer/batch/status');
export const runBatch = () => api.post('/officer/batch/run');
export const getUniversityProjects = () => api.get('/university/projects');
export const getCSRChallenges = () => api.get('/csr/challenges');
export const getDashboardStats = () => api.get('/dashboard/stats');
export const loginUser = (credentials) => api.post('/auth/login', credentials);

export default api;
