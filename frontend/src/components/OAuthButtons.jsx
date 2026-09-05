import React, { useState } from 'react';
import { Chrome, Facebook, Loader2 } from 'lucide-react';
import api from '../services/api';

const PROVIDERS = [
  { id: 'google', label: 'Google', Icon: Chrome },
  { id: 'facebook', label: 'Facebook', Icon: Facebook },
];

/**
 * OAuthButtons — "Continue with Google / Facebook".
 *
 * Backend-mediated flow (nothing secret ever touches the browser):
 *   1. Frontend asks the API for a provider authorization URL:
 *        GET /api/v1/auth/oauth/{google|facebook}/url?next=/app/citizen
 *   2. Browser redirects there; the provider sends the user back to the
 *      backend callback, which finishes with a redirect to
 *        /login?token=<jwt>&role=<role>&org=<org>&next=<next>
 *   3. Login consumes those params via `consumeOAuthCallback` and opens
 *      the correct workspace.
 *
 * Until the backend ships those endpoints, the buttons degrade with an
 * honest notice instead of a dead redirect.
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
      if (err.response?.status === 404) {
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
      <div className="grid grid-cols-2 gap-2" role="group" aria-label="Continue with a social account">
        {PROVIDERS.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => start({ id, label })}
            disabled={busy !== null}
            className="btn-secondary flex items-center justify-center gap-2 !py-2.5 disabled:opacity-60"
          >
            {busy === id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" aria-hidden />}
            {label}
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

/** Reads the backend OAuth callback params (?token=&role=&org=&error=). */
export function consumeOAuthCallback(searchParams) {
  if (searchParams.get('error')) {
    return { error: searchParams.get('error_description') || 'Your social sign-in was not completed. Try email sign-in instead.' };
  }
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
