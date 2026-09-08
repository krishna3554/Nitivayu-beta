import React, { useState } from 'react';
import { Chrome, Loader2 } from 'lucide-react';
import api from '../services/api';

// Google-only deployment (owner U4): Facebook Graph v18.0 is retired, so the
// button is removed. The backend still answers 501 for /facebook/url with a
// "retired" message for old links.
const PROVIDERS = [
  { id: 'google', label: 'Google', Icon: Chrome },
];

/**
 * OAuthButtons — "Continue with Google".
 *
 * Backend-mediated flow (nothing secret ever touches the browser):
 *   1. Frontend asks the API for a provider authorization URL:
 *        GET /api/v1/auth/oauth/google/url?next=/app/citizen
 *   2. Browser redirects there; the provider sends the user back to the
 *      backend callback, which finishes with a one-time code redirect to
 *        /login?code=<one-time>&next=<next>   (JWT never in query/logs, B2.7)
 *   3. Login exchanges the code once via POST /auth/oauth/consume and opens
 *      the correct workspace.
 *
 * Until GOOGLE_* is configured the backend answers 501 and the buttons
 * degrade with an honest notice instead of a dead redirect.
 */
export default function OAuthButtons({ next = '', mode = 'signin' }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');

  const start = async (provider) => {
    setBusy(provider.id);
    setError('');
    try {
      const { data } = await api.get(`/auth/oauth/${provider.id}/url`, {
        params: next ? { next } : {},
      });
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      setError(`Your ${provider.label} sign-in link came back empty. Use email ${mode === 'signup' ? 'registration' : 'sign-in'} for this demo.`);
    } catch (err) {
      if (err.response?.status === 404 || err.response?.status === 501) {
        setError(`${provider.label} ${mode === 'signup' ? 'registration' : 'sign-in'} is being connected — use email ${mode === 'signup' ? 'registration' : 'sign-in'} for this demo.`);
      } else {
        setError(err.response?.data?.detail || `Could not reach ${provider.label}. Try again in a moment.`);
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="grid grid-cols-1 gap-2" role="group" aria-label="Continue with a social account">
        {PROVIDERS.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => start({ id, label })}
            disabled={busy !== null}
            className="btn-secondary flex items-center justify-center gap-2 !py-2.5 disabled:opacity-60"
          >
            {busy === id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" aria-hidden />}
            Continue with {label}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div className="my-5 flex items-center gap-3" aria-hidden>
        <span className="h-px flex-1 bg-border" />
        <span className="type-caption text-zinc-400">or continue with email</span>
        <span className="h-px flex-1 bg-border" />
      </div>
    </div>
  );
}

/** Exchange a one-time OAuth `code` for the session (B2.7). Single-use, 60s TTL. */
export async function exchangeOAuthCode(code) {
  const { data } = await api.post('/auth/oauth/consume', { code });
  if (!data?.access_token) throw new Error('Sign-in code did not return a session.');
  return {
    session: {
      token: data.access_token,
      role: data.role || data.workspace_type || 'citizen',
      workspace: undefined, // resolved by loginWithSession via roleToWorkspace
      displayName: data.display_name || data.organization_name || '',
      orgName: data.organization_name || '',
      organizationId: data.organization_id || null,
      next: data.next || '',
    },
  };
}

/** Reads the backend OAuth callback params (?code= new, ?token= legacy, ?error=). */
export function consumeOAuthCallback(searchParams) {
  if (searchParams.get('error')) {
    return { error: searchParams.get('error_description') || 'Your social sign-in was not completed. Try email sign-in instead.' };
  }
  const code = searchParams.get('code');
  if (code) return { code };
  // Legacy compat: pre-B2.7 links carried ?token=&role=&org=. Accept them once
  // so in-flight sign-ins survive the deploy, then the backend stops sending them.
  const token = searchParams.get('token');
  if (!token) return null;
  return {
    session: {
      token,
      role: searchParams.get('role') || searchParams.get('workspace') || 'citizen',
      orgName: searchParams.get('org') || '',
      organizationId: searchParams.get('organization_id') || null,
    },
  };
}
