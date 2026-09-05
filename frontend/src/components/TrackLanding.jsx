import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Radar, ShieldCheck, GraduationCap } from 'lucide-react';

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

      {/* How tracking works — fills the page with intent, not whitespace */}
      <div className="mx-auto mt-12 max-w-4xl">
        <p className="type-caption text-center text-primary">How tracking works</p>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {[
            { icon: Radar, title: 'Submit once', copy: 'Your report is ingested and structured instantly — the token is your public receipt.' },
            { icon: ShieldCheck, title: 'Officer review ≤ 72h', copy: 'A nodal officer verifies the AI match and routes your challenge to a university.' },
            { icon: GraduationCap, title: 'Follow to resolution', copy: 'Watch M1–M3 milestones land here until field validation closes your report.' },
          ].map(({ icon: Icon, title, copy }) => (
            <div key={title} className="card p-5">
              <span className="flex h-10 w-10 items-center justify-center rounded-md bg-surface-muted text-ink"><Icon className="h-5 w-5" /></span>
              <h2 className="mt-4 font-medium-plus">{title}</h2>
              <p className="type-body-sm mt-1.5 text-zinc-500">{copy}</p>
            </div>
          ))}
        </div>
        <p className="type-body-sm mt-6 text-center text-zinc-500">
          Lost your token? File a new report — duplicates are merged automatically. <Link to="/how-it-works" className="link-inline !text-sm font-medium-plus">How the pipeline works</Link>
        </p>
      </div>
    </div>
  );
}
