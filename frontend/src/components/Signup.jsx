import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Smartphone, Ticket, Mail, Lock, User } from 'lucide-react';
import { useAuth } from '../lib/auth';
import OAuthButtons from './OAuthButtons';
import api from '../services/api';
import { JHARKHAND_DISTRICTS } from './ui/EvidenceComposer';

/** Signup — citizen self-serve (phone OTP or email) + institutional invite acceptance. */
export default function Signup() {
  const navigate = useNavigate();
  const { loginWithSession } = useAuth();
  const [tab, setTab] = useState('phone');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [phone, setPhone] = useState('');
  const [district, setDistrict] = useState('Ranchi');
  const [otpSent, setOtpSent] = useState(false);
  const [emailForm, setEmailForm] = useState({ name: '', email: '', password: '' });
  const [invite, setInvite] = useState({ token: '', email: '', password: '', name: '' });

  const requestSignupOtp = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setNotice('');
    try {
      await api.post('/auth/request-otp', { phone, district });
      setOtpSent(true);
      setNotice(`We sent a code to ${phone}. Enter it on the sign-in page to finish creating your account.`);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Citizen OTP signup is being connected (Phase 1). You can already report with a tracking token — no account needed for the demo.');
      } else setError(err.response?.data?.detail || 'Could not start signup. Try again in a minute.');
    } finally { setLoading(false); }
  };

  const registerWithEmail = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setNotice('');
    try {
      const { data } = await api.post('/auth/register', { ...emailForm, district, workspace_type: 'citizen' });
      if (data?.access_token) {
        // Backend logged us in immediately — open the citizen workspace.
        loginWithSession({
          token: data.access_token,
          role: data.role || data.workspace_type || 'citizen',
          orgName: data.organization_name || '',
          organizationId: data.organization_id || null,
        });
        navigate('/app/citizen');
      } else {
        setNotice('Account created. Sign in with your new email and password.');
        setTimeout(() => navigate('/login'), 1500);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Email registration is being connected (Phase 1). For this demo, report with a tracking token or use phone OTP once it lands.');
      } else {
        setError(err.response?.data?.detail || 'Could not create your account. Try again in a moment.');
      }
    } finally { setLoading(false); }
  };

  const acceptInvite = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setNotice('');
    try {
      await api.post('/auth/accept-invite', invite);
      setNotice('Invite accepted. Sign in with your new credentials.');
      setTimeout(() => navigate('/login'), 1200);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Invite acceptance connects with institutional hardening (Phase 6). Ask your admin to provision your account directly for now.');
      } else setError(err.response?.data?.detail || 'That invite did not match. Check the token and email.');
    } finally { setLoading(false); }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] max-w-content items-center justify-center px-4 py-12 md:px-6">
      <div className="card w-full max-w-md p-8">
        <h1 className="text-2xl font-medium-plus tracking-tight">Create your account</h1>
        <p className="type-body-sm mt-1 text-zinc-500">One account, one workspace. Citizens self-serve with phone or email; institutions join by invite.</p>

        <div className="mb-6 mt-6">
          <OAuthButtons mode="signup" />
        </div>

        <div className="mb-6 grid grid-cols-3 gap-1 rounded-md bg-surface-muted p-1" role="tablist" aria-label="Signup path">
          <button type="button" role="tab" aria-selected={tab === 'phone'} onClick={() => setTab('phone')}
            className={`rounded-md px-3 py-2 text-sm font-medium-plus ${tab === 'phone' ? 'bg-white text-ink shadow-sm' : 'text-zinc-500'}`}>Phone</button>
          <button type="button" role="tab" aria-selected={tab === 'email'} onClick={() => setTab('email')}
            className={`rounded-md px-3 py-2 text-sm font-medium-plus ${tab === 'email' ? 'bg-white text-ink shadow-sm' : 'text-zinc-500'}`}>Email</button>
          <button type="button" role="tab" aria-selected={tab === 'invite'} onClick={() => setTab('invite')}
            className={`rounded-md px-3 py-2 text-sm font-medium-plus ${tab === 'invite' ? 'bg-white text-ink shadow-sm' : 'text-zinc-500'}`}>Invite</button>
        </div>

        {tab === 'phone' ? (
          <form onSubmit={requestSignupOtp} className="space-y-4">
            <div>
              <label htmlFor="su-phone" className="type-label-sm">Phone number</label>
              <div className="relative mt-1.5">
                <Smartphone className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="su-phone" type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" className="input pl-10" />
              </div>
            </div>
            <div>
              <label htmlFor="su-district" className="type-label-sm">Home district <span className="text-zinc-400">(optional — speeds up routing)</span></label>
              <select id="su-district" value={district} onChange={(e) => setDistrict(e.target.value)} className="input mt-1.5">
                {JHARKHAND_DISTRICTS.map((d) => <option key={d}>{d}</option>)}
              </select>
            </div>
            {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
            {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice} {otpSent && <Link to="/login" className="link-inline !text-sm font-medium-plus">Go to sign-in</Link>}</p>}
            <button type="submit" disabled={loading} className="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-70">
              {loading ? 'Sending code…' : <>Create account <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
        ) : tab === 'email' ? (
          <form onSubmit={registerWithEmail} className="space-y-4">
            <div>
              <label htmlFor="su-name" className="type-label-sm">Full name</label>
              <div className="relative mt-1.5">
                <User className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="su-name" required value={emailForm.name} onChange={(e) => setEmailForm({ ...emailForm, name: e.target.value })} placeholder="Your name" className="input pl-10" />
              </div>
            </div>
            <div>
              <label htmlFor="su-email" className="type-label-sm">Email address</label>
              <div className="relative mt-1.5">
                <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="su-email" type="email" required value={emailForm.email} onChange={(e) => setEmailForm({ ...emailForm, email: e.target.value })} placeholder="you@example.com" className="input pl-10" />
              </div>
            </div>
            <div>
              <label htmlFor="su-pass" className="type-label-sm">Password <span className="text-zinc-400">(min 8 characters)</span></label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="su-pass" type="password" required minLength={8} value={emailForm.password} onChange={(e) => setEmailForm({ ...emailForm, password: e.target.value })} placeholder="••••••••" className="input pl-10" />
              </div>
            </div>
            <div>
              <label htmlFor="su-edistrict" className="type-label-sm">Home district <span className="text-zinc-400">(optional — speeds up routing)</span></label>
              <select id="su-edistrict" value={district} onChange={(e) => setDistrict(e.target.value)} className="input mt-1.5">
                {JHARKHAND_DISTRICTS.map((d) => <option key={d}>{d}</option>)}
              </select>
            </div>
            {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
            {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}
            <button type="submit" disabled={loading} className="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-70">
              {loading ? 'Creating account…' : <>Create account <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
        ) : (
          <form onSubmit={acceptInvite} className="space-y-4">
            <div>
              <label htmlFor="inv-token" className="type-label-sm">Invite token</label>
              <div className="relative mt-1.5">
                <Ticket className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="inv-token" required value={invite.token} onChange={(e) => setInvite({ ...invite, token: e.target.value })} placeholder="From your admin’s email" className="input pl-10 font-mono" />
              </div>
            </div>
            <div>
              <label htmlFor="inv-email" className="type-label-sm">Work email</label>
              <input id="inv-email" type="email" required value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} placeholder="you@university.ac.in" className="input mt-1.5" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="inv-name" className="type-label-sm">Full name</label>
                <input id="inv-name" required value={invite.name} onChange={(e) => setInvite({ ...invite, name: e.target.value })} className="input mt-1.5" />
              </div>
              <div>
                <label htmlFor="inv-pass" className="type-label-sm">Password</label>
                <input id="inv-pass" type="password" required minLength={8} value={invite.password} onChange={(e) => setInvite({ ...invite, password: e.target.value })} className="input mt-1.5" />
              </div>
            </div>
            {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
            {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}
            <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-70">{loading ? 'Accepting…' : 'Accept invite'}</button>
            <p className="type-body-sm text-zinc-500">University addresses use .ac.in verification; corporate addresses verify against the invited organization.</p>
          </form>
        )}

        <p className="type-body-sm mt-6 text-center text-zinc-500">Already have an account? <Link to="/login" className="link-inline !text-sm font-medium-plus">Sign in</Link></p>
      </div>
    </div>
  );
}
