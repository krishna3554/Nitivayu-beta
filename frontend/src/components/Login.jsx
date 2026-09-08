import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Lock, Mail, ArrowRight, Smartphone } from 'lucide-react';
import { useAuth } from '../lib/auth';
import OAuthButtons, { consumeOAuthCallback, exchangeOAuthCode } from './OAuthButtons';
import api, { getDemoAccounts } from '../services/api';

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

  // Demo credentials (seeded workspaces) come from the backend and only
  // exist when DEMO_MODE is on — production builds hide this panel entirely.
  const [demoAccounts, setDemoAccounts] = useState(null);
  useEffect(() => {
    let live = true;
    getDemoAccounts().then(({ data }) => { if (live) setDemoAccounts(data?.accounts || []); }).catch(() => { if (live) setDemoAccounts([]); });
    return () => { live = false; };
  }, []);
  const fillDemo = (acc) => {
    setMode('institution');
    setEmail(acc.email);
    setPassword(acc.password);
    setError('');
  };

  const goWorkspace = (session) => {
    const map = { citizen: '/app/citizen', officer: '/app/officer', university: '/app/university', corporate: '/app/corporate', admin: '/app/admin' };
    navigate(next || map[session.workspace] || '/app/citizen');
  };

  // Backend OAuth callback (?code= one-time, ?token= legacy) lands here.
  useEffect(() => {
    let cancelled = false;
    const result = consumeOAuthCallback(params);
    if (result?.error) {
      setError(result.error);
      return undefined;
    }
    if (result?.session) {
      goWorkspace(loginWithSession(result.session));
      return undefined;
    }
    if (result?.code) {
      setLoading(true);
      exchangeOAuthCode(result.code)
        .then(({ session }) => {
          if (cancelled) return;
          // Strip the single-use code from the address bar (B2.7).
          const clean = new URLSearchParams(params);
          clean.delete('code');
          navigate({ pathname: '/login', search: clean.toString() ? `?${clean}` : '' }, { replace: true });
          goWorkspace(loginWithSession(session));
        })
        .catch(() => {
          if (!cancelled) setError('That Google sign-in link expired or was already used. Try again.');
        })
        .finally(() => { if (!cancelled) setLoading(false); });
      return () => { cancelled = true; };
    }
    return undefined;
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
      const { data } = await api.post('/auth/request-otp', { phone });
      setOtpSent(true);
      setNotice(data?.dev_code
        ? `Demo code for ${phone}: ${data.dev_code} (dev mode — expires in 10 minutes).`
        : `We sent a 6-digit code to ${phone}. It expires in 10 minutes.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send the code. Try again in a minute.');
    } finally { setLoading(false); }
  };

  const verifyOtp = async (e) => {
    e.preventDefault();
    setLoading(true); setError('');
    try {
      const { data } = await api.post('/auth/verify-otp', { phone, code: otp });
      const session = loginWithSession({ token: data.access_token, role: 'citizen', displayName: data.display_name || '', organizationId: null, orgName: '' });
      goWorkspace(session);
    } catch (err) {
      setError(err.response?.data?.detail || 'That code did not match. Check the SMS and try again.');
    } finally { setLoading(false); }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] max-w-content items-center justify-center px-4 py-12 md:px-6">
      <div className="card grid w-full max-w-4xl overflow-hidden md:grid-cols-[1fr_1.15fr]">
        {/* Brand panel — fills the wide-screen void with context */}
        <div className="hidden flex-col justify-between bg-ink p-8 text-white md:flex">
          <img
            src="/nitivayu-mark.png"
            srcSet="/nitivayu-mark-64.png 1x, /nitivayu-mark.png 2x"
            alt="Nitivayu logo"
            width={40}
            height={40}
            className="h-10 w-10 rounded-md"
          />
          <div>
            <p className="type-caption text-white/50">One account · one workspace</p>
            <h2 className="mt-3 text-3xl font-medium-plus tracking-tight">Helplines close tickets. You solve problems.</h2>
            <ul className="mt-6 space-y-4">
              {[
                ['Citizens', 'Report in Hindi, Hinglish, or English — your token arrives in seconds.'],
                ['Officers', 'Verify AI-structured matches inside a 72-hour SLA.'],
                ['Universities & CSR', 'Build M1–M3 milestones with funding you can audit.'],
              ].map(([title, copy]) => (
                <li key={title} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden />
                  <p className="text-sm text-white/70"><strong className="font-medium-plus text-white">{title} — </strong>{copy}</p>
                </li>
              ))}
            </ul>
          </div>
          <p className="type-body-sm text-white/40">Your tracking token stays public; your account stays private.</p>
        </div>

        {/* Form panel */}
        <div className="p-8">
        <div className="mb-6 text-center md:hidden">
          <img
            src="/nitivayu-mark.png"
            srcSet="/nitivayu-mark-64.png 1x, /nitivayu-mark.png 2x"
            alt="Nitivayu logo"
            width={48}
            height={48}
            className="mx-auto h-12 w-12 rounded-md"
          />
        </div>
        <div className="mb-6 text-center md:text-left">
          <h1 className="text-2xl font-medium-plus tracking-tight">Sign in to Nitivayu</h1>
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

        {demoAccounts !== null && demoAccounts.length > 0 && (
        <div className="mt-6 border-t border-border pt-4">
          <p className="type-caption text-zinc-400">Demo accounts — tap to fill</p>
          <ul className="mt-2 space-y-1.5">
            {demoAccounts.map((acc) => (
              <li key={acc.email}>
                <button
                  type="button"
                  onClick={() => fillDemo(acc)}
                  title={`Fill ${acc.email}`}
                  className="flex w-full items-center justify-between gap-2 rounded-md border border-border bg-surface-muted px-3 py-1.5 text-left hover:border-primary hover:bg-primary-subtle"
                >
                  <span className="type-body-sm font-medium-plus text-ink">{acc.role}</span>
                  <span className="truncate font-mono text-xs text-zinc-500">{acc.email} · {acc.note || acc.password}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="type-body-sm mt-2 text-zinc-500">Google sign-in works with any Gmail (lands in Citizen). Officer/university/CSR via Google need their Gmail linked — ask me to link one.</p>
        </div>
        )}
        </div>
      </div>
    </div>
  );
}
