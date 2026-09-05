import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Lock, Mail, ArrowRight, Smartphone } from 'lucide-react';
import { useAuth } from '../lib/auth';
import OAuthButtons, { consumeOAuthCallback } from './OAuthButtons';
import api from '../services/api';

export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { login, loginWithSession } = useAuth();
  const [mode, setMode] = useState('institution'); // institution | citizen
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);

  const next = params.get('next') || '';

  const goWorkspace = (session) => {
    const map = { citizen: '/app/citizen', officer: '/app/officer', university: '/app/university', corporate: '/app/corporate', admin: '/app/admin' };
    navigate(next || map[session.workspace] || '/app/citizen');
  };

  // Backend OAuth callback (?token=&role=&org=) lands here.
  useEffect(() => {
    const result = consumeOAuthCallback(params);
    if (result?.error) setError(result.error);
    else if (result?.session) goWorkspace(loginWithSession(result.session));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleInstitutionLogin = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const session = await login({ email, password });
      goWorkspace(session);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to sign in. Check your email and password.');
    } finally { setLoading(false); }
  };

  const requestOtp = async (e) => {
    e.preventDefault();
    setLoading(true); setError(''); setNotice('');
    try {
      await api.post('/auth/request-otp', { phone });
      setOtpSent(true);
      setNotice(`We sent a 6-digit code to ${phone}. It expires in 10 minutes.`);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Phone OTP sign-in is being connected (Phase 1). For this demo, use email sign-in or continue as a guest with your tracking token.');
      } else {
        setError(err.response?.data?.detail || 'Could not send the code. Try again in a minute.');
      }
    } finally { setLoading(false); }
  };

  const verifyOtp = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const { data } = await api.post('/auth/verify-otp', { phone, code: otp });
      const session = loginWithSession({ token: data.access_token, role: 'citizen', organizationId: null, orgName: '' });
      goWorkspace(session);
    } catch (err) {
      setError(err.response?.data?.detail || 'That code did not match. Check the SMS and try again.');
    } finally { setLoading(false); }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] max-w-content items-center justify-center px-4 py-12 md:px-6">
      <div className="card w-full max-w-md p-8">
        <div className="mb-6 text-center">
          <img
            src="/nitivayu-mark.png"
            srcSet="/nitivayu-mark-64.png 1x, /nitivayu-mark.png 2x"
            alt="Nitivayu logo"
            width={48}
            height={48}
            className="mx-auto h-12 w-12 rounded-md"
          />
          <h1 className="mt-4 text-2xl font-medium-plus tracking-tight">Sign in to Nitivayu</h1>
          <p className="type-body-sm mt-1 text-zinc-500">You land in your workspace — never a shared dashboard.</p>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-1 rounded-md bg-surface-muted p-1" role="tablist" aria-label="Sign-in method">
          <button type="button" role="tab" aria-selected={mode === 'citizen'} onClick={() => setMode('citizen')}
            className={`rounded-md px-3 py-2 text-sm font-medium-plus ${mode === 'citizen' ? 'bg-white text-ink shadow-sm' : 'text-zinc-500'}`}>Citizen · OTP</button>
          <button type="button" role="tab" aria-selected={mode === 'institution'} onClick={() => setMode('institution')}
            className={`rounded-md px-3 py-2 text-sm font-medium-plus ${mode === 'institution' ? 'bg-white text-ink shadow-sm' : 'text-zinc-500'}`}>Officer · Univ · CSR</button>
        </div>

        <OAuthButtons next={next} mode="signin" />

        {mode === 'citizen' ? (
          !otpSent ? (
            <form onSubmit={requestOtp} className="space-y-4">
              <div>
                <label htmlFor="login-phone" className="type-label-sm">Phone number</label>
                <div className="relative mt-1.5">
                  <Smartphone className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                  <input id="login-phone" type="tel" required placeholder="+91 98765 43210" value={phone}
                    onChange={(e) => setPhone(e.target.value)} className="input pl-10" />
                </div>
                <p className="type-body-sm mt-1.5 text-zinc-500">No password needed. Reporting history, SMS updates, and spam protection come with your account.</p>
              </div>
              {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
              {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}
              <button type="submit" disabled={loading} className="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-70">
                {loading ? 'Sending code…' : <>Send code <ArrowRight className="h-4 w-4" /></>}
              </button>
              <p className="type-body-sm text-center text-zinc-500">New here? <Link to="/signup" className="link-inline !text-sm font-medium-plus">Create a citizen account</Link></p>
            </form>
          ) : (
            <form onSubmit={verifyOtp} className="space-y-4">
              <div>
                <label htmlFor="login-otp" className="type-label-sm">6-digit code</label>
                <input id="login-otp" inputMode="numeric" pattern="[0-9]{4,8}" required placeholder="••••••" value={otp}
                  onChange={(e) => setOtp(e.target.value)} className="input mt-1.5 text-center font-mono text-xl tracking-[0.3em]" />
              </div>
              {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
              {notice && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full disabled:opacity-70">{loading ? 'Verifying…' : 'Verify & continue'}</button>
              <button type="button" onClick={() => setOtpSent(false)} className="link-inline w-full text-center !text-sm">Use a different number</button>
            </form>
          )
        ) : (
          <form onSubmit={handleInstitutionLogin} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="type-label-sm">Work email</label>
              <div className="relative mt-1.5">
                <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="login-email" type="email" required placeholder="officer@nitivayu.gov.in" value={email}
                  onChange={(e) => setEmail(e.target.value)} className="input pl-10" />
              </div>
            </div>
            <div>
              <label htmlFor="login-password" className="type-label-sm">Password</label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
                <input id="login-password" type="password" required placeholder="••••••••" value={password}
                  onChange={(e) => setPassword(e.target.value)} className="input pl-10" />
              </div>
              <p className="type-body-sm mt-1.5 text-zinc-500">Officer, university, and CSR accounts are invite-only — your workspace opens automatically.</p>
            </div>
            {error && <p role="alert" className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
            <button type="submit" disabled={loading} className="btn-primary flex w-full items-center justify-center gap-2 disabled:opacity-70">
              {loading ? 'Signing in…' : <>Sign in <ArrowRight className="h-4 w-4" /></>}
            </button>
          </form>
        )}

        <div className="mt-6 border-t border-border pt-4">
          <p className="type-caption text-zinc-400">Demo accounts</p>
          <ul className="type-body-sm mt-2 space-y-1 font-mono text-zinc-500">
            <li>officer@nitivayu.gov.in</li>
            <li>iic.head@bitmesra.ac.in</li>
            <li>csr@tatasteel.com</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
