import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

/** Public tracker entry — a tracking token is the access control, not a login. */
export default function TrackLanding() {
  const [token, setToken] = useState('');
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-content px-4 py-14 md:px-6">
      <div className="mx-auto max-w-xl">
        <p className="badge">Live tracker</p>
        <h1 className="type-display-md mt-4 text-ink">Where is your report?</h1>
        <p className="type-body-md mt-3 text-zinc-500">Enter the token you received at submission (e.g. NITIVAYU-2026-JH-XXXXXX). No sign-in needed — share it with anyone.</p>
        <form
          className="card mt-6 flex flex-col gap-3 p-5 sm:flex-row"
          onSubmit={(e) => { e.preventDefault(); if (token.trim()) navigate(`/track/${token.trim()}`); }}
        >
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="NITIVAYU-2026-JH-XXXXXX"
            aria-label="Tracking token"
            className="input font-mono"
          />
          <button type="submit" disabled={!token.trim()} className="btn-primary inline-flex shrink-0 items-center justify-center gap-2 disabled:opacity-60">
            Track <ArrowRight className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
