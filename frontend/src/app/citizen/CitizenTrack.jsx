import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export default function CitizenTrack() {
  const [token, setToken] = useState('');
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="type-display-md !text-3xl">Track a report</h1>
      <p className="type-body-md mt-2 text-zinc-500">Your token works for anyone you share it with — no sign-in needed.</p>
      <form className="card mt-5 flex flex-col gap-3 p-5 sm:flex-row"
        onSubmit={(e) => { e.preventDefault(); if (token.trim()) navigate(`/track/${token.trim()}`); }}>
        <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="NITIVAYU-2026-JH-XXXXXX" aria-label="Tracking token" className="input font-mono" />
        <button type="submit" disabled={!token.trim()} className="btn-primary inline-flex shrink-0 items-center justify-center gap-2 disabled:opacity-60">
          Track <ArrowRight className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
