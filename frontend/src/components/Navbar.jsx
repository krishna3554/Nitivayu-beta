import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Menu, X, Search } from 'lucide-react';
import { useAuth } from '../lib/auth';

const NAV = [
  { to: '/how-it-works', label: 'How it works' },
  { to: '/impact', label: 'Impact' },
  { to: '/about', label: 'About' },
  { to: '/track', label: 'Track' },
];

/** Fireworks navbar: 73px, white, sticky, 1px hairline, 4 nav links + one violet CTA. */
export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState('');
  const navigate = useNavigate();
  const { session, workspaceHome, logout } = useAuth();

  return (
    <header className="navbar-fireworks">
      <div className="mx-auto flex h-full max-w-content items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2" aria-label="Nitivayu home">
            <img
              src="/nitivayu-mark.png"
              srcSet="/nitivayu-mark-64.png 1x, /nitivayu-mark.png 2x"
              alt="Nitivayu logo"
              width={32}
              height={32}
              className="h-8 w-8 rounded-md"
            />
            <span className="text-base font-medium-plus tracking-tight text-ink">Nitivayu</span>
          </Link>
          <nav className="hidden items-center gap-6 md:flex" aria-label="Primary">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} className="type-nav-link text-ink hover:text-primary">{n.label}</Link>
            ))}
          </nav>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <form
            className="hidden items-center lg:flex"
            onSubmit={(e) => { e.preventDefault(); if (token.trim()) navigate(`/track/${token.trim()}`); }}
            role="search"
            aria-label="Track by token"
          >
            <span className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400" />
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="NITIVAYU-2026-…"
                aria-label="Tracking token"
                className="input !w-44 !py-1.5 !text-sm pl-8 font-mono"
              />
            </span>
          </form>
          {session ? (
            <>
              <Link to={workspaceHome()} className="btn-primary !py-2.5">Open workspace</Link>
              <button type="button" onClick={logout} className="type-nav-link text-zinc-500 hover:text-ink">Sign out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="type-nav-link text-ink hover:text-primary">Sign in</Link>
              <Link to="/signup" className="btn-primary !py-2.5">Sign up</Link>
            </>
          )}
        </div>

        <button type="button" className="rounded-md border border-border p-2 md:hidden" aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen((v) => !v)}>
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-border bg-white px-4 py-4 md:hidden">
          <nav className="grid gap-1" aria-label="Mobile">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} onClick={() => setOpen(false)} className="type-nav-link rounded-md px-2 py-2.5 text-ink hover:bg-surface-muted">{n.label}</Link>
            ))}
            {!session && <Link to="/login" onClick={() => setOpen(false)} className="type-nav-link rounded-md px-2 py-2.5 text-ink">Sign in</Link>}
            {session ? (
              <Link to={workspaceHome()} onClick={() => setOpen(false)} className="btn-primary mt-2 text-center">Open workspace</Link>
            ) : (
              <Link to="/signup" onClick={() => setOpen(false)} className="btn-primary mt-2 text-center">Sign up</Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
