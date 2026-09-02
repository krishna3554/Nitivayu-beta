import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, MapPin, Loader2, CheckCircle2, Copy } from 'lucide-react';
import { submitComplaint } from '../services/api';

export default function CitizenIntakeForm() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [successToken, setSuccessToken] = useState(null);
  const [formData, setFormData] = useState({
    description: '',
    language: 'english',
    district: 'Patna',
    block: 'Sadar',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.description.trim()) return;
    
    setLoading(true);
    try {
      const payload = new FormData();
      payload.append('raw_text', formData.description);
      payload.append('language_pref', formData.language);
      payload.append('district', formData.district);
      payload.append('block', formData.block);
      const res = await submitComplaint(payload);
      setSuccessToken(res.data.tracking_token);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const copyToken = () => {
    navigator.clipboard.writeText(successToken);
    alert('Token copied!');
  };

  if (successToken) {
    return (
      <div className="max-w-md mx-auto mt-12 p-6 bg-white rounded-xl shadow-sm border border-emerald-100 text-center">
        <CheckCircle2 className="w-16 h-16 text-emerald-600 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-zinc-900 mb-2">Issue Submitted</h2>
        <p className="text-zinc-600 mb-6">Your issue is now in our triaging pipeline.</p>
        
        <div className="bg-slate-50 p-4 rounded-lg mb-6 flex items-center justify-between border border-slate-200">
          <span className="font-mono font-bold text-lg text-zinc-900 tracking-wider">{successToken}</span>
          <button onClick={copyToken} className="p-2 text-zinc-500 hover:text-zinc-900 transition-colors">
            <Copy className="w-5 h-5" />
          </button>
        </div>
        
        <button 
          onClick={() => navigate(`/track/${successToken}`)}
          className="w-full py-3 bg-zinc-900 text-white rounded-lg font-medium hover:bg-zinc-800 transition-colors"
        >
          Track Progress
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto mt-8 p-6 bg-white rounded-xl shadow-sm border border-slate-200">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-900">Report an Issue</h1>
        <p className="text-zinc-600 text-sm mt-1">Describe the civic problem in your own words.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-zinc-900">Language Preference</span>
          </label>
          <div className="flex gap-2">
            {['english', 'hindi', 'hinglish'].map(lang => (
              <button
                key={lang}
                type="button"
                onClick={() => setFormData({...formData, language: lang})}
                className={`px-4 py-2 text-sm font-medium rounded-md capitalize flex-1 border ${formData.language === lang ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'bg-white border-slate-200 text-zinc-600 hover:bg-slate-50'}`}
              >
                {lang}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-900 mb-2">Describe the Problem</label>
          <textarea
            required
            rows={5}
            className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all resize-none"
            placeholder="E.g., The road near the market is completely broken for 3 months..."
            value={formData.description}
            onChange={(e) => setFormData({...formData, description: e.target.value})}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-zinc-900 mb-2">District</label>
            <select 
              className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              value={formData.district}
              onChange={(e) => setFormData({...formData, district: e.target.value})}
            >
              <option value="Patna">Patna</option>
              <option value="Gaya">Gaya</option>
              <option value="Muzaffarpur">Muzaffarpur</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-900 mb-2">Block/Area</label>
            <select 
              className="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              value={formData.block}
              onChange={(e) => setFormData({...formData, block: e.target.value})}
            >
              <option value="Sadar">Sadar</option>
              <option value="City">City</option>
              <option value="Danapur">Danapur</option>
            </select>
          </div>
        </div>

        <div className="border-2 border-dashed border-slate-300 rounded-lg p-6 text-center bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer">
          <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
          <p className="text-sm font-medium text-zinc-700">Upload Photo (Optional)</p>
          <p className="text-xs text-slate-500 mt-1">Drag and drop or click to select</p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 transition-colors flex items-center justify-center disabled:opacity-70"
        >
          {loading ? (
            <><Loader2 className="w-5 h-5 animate-spin mr-2" /> Submitting...</>
          ) : 'Submit Issue'}
        </button>
      </form>
    </div>
  );
}
