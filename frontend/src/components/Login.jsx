import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, Mail, ArrowRight } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });

  const handleLogin = (e) => {
    e.preventDefault();
    setLoading(true);
    // Mock login logic
    setTimeout(() => {
      localStorage.setItem('nitivayu_token', 'mock-jwt-token');
      // Simple routing based on email domain to demonstrate roles
      if (formData.email.includes('admin') || formData.email.includes('officer')) {
        navigate('/officer');
      } else if (formData.email.includes('uni')) {
        navigate('/university');
      } else if (formData.email.includes('csr')) {
        navigate('/csr');
      } else {
        navigate('/dashboard');
      }
      setLoading(false);
    }, 1000);
  };

  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
        <div className="text-center mb-8">
          <div className="mx-auto w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center text-white text-2xl font-bold mb-4 shadow-lg shadow-indigo-200">
            N
          </div>
          <h2 className="text-2xl font-bold text-zinc-900">Sign in to Nitivayu</h2>
          <p className="text-sm text-zinc-500 mt-2">Access your specialized portal</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-zinc-900 mb-2">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
              <input 
                type="email" 
                required
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-colors outline-none" 
                placeholder="officer@nitivayu.gov.in"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-900 mb-2">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
              <input 
                type="password" 
                required
                className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-colors outline-none" 
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({...formData, password: e.target.value})}
              />
            </div>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-zinc-900 hover:bg-zinc-800 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-70"
          >
            {loading ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <>Sign In <ArrowRight className="w-4 h-4" /></>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-slate-100 text-xs text-zinc-500 flex justify-between">
          <p>Mock Accounts:</p>
          <div className="text-right space-y-1">
            <p>officer@nitivayu.gov.in</p>
            <p>prof@iitp.ac.in</p>
            <p>csr@tata.com</p>
          </div>
        </div>
      </div>
    </div>
  );
}
