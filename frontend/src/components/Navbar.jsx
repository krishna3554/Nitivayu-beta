import React, { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Menu, X, Search, ChevronDown, LogOut, LayoutDashboard, FolderOpen } from 'lucide-react';
import { useAuth } from '../lib/auth';

const NAV = [
  { to: '/how-it-works', label: 'How it works' },
  { to: '/impact', label: 'Impact' },
  { to: '/about', label: 'About' },
  { to: '/track', label: 'Track' },
];

// Same workspace language as the AppShell sidebar titles.
const WORKSPACE_TITLES = {
  citizen: 'Citizen App',
  officer: 'Officer Console',
  university: 'University Workspace',
  corporate: 'Corporate Workspace',
  admin: 'Admin Control Plane',
};

function initialsFor(name) {
  const words = String(name || '').split(/\s+/).filter(Boolean);
  if (!words.length) return '?';
  return (words[0][0] + (words[1]?.[0] || '')).toUpperCase();
}

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
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) => `type-nav-link ${isActive ? 'text-primary' : 'text-ink hover:text-primary'}`}
              >
                {n.label}
              </NavLink>
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
            <AccountMenu
              displayName={session.displayName || session.orgName || WORKSPACE_TITLES[session.workspace] || 'Workspace'}
              workspaceLabel={WORKSPACE_TITLES[session.workspace] || 'Workspace'}
              workspaceHome={workspaceHome()}
              showReports={(session.workspace || '') === 'citizen'}
              onLogout={logout}
            />
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
              <NavLink
                key={n.to}
                to={n.to}
                onClick={() => setOpen(false)}
                className={({ isActive }) => `type-nav-link rounded-md px-2 py-2.5 ${isActive ? 'bg-primary-subtle text-primary' : 'text-ink hover:bg-surface-muted'}`}
              >
                {n.label}
              </NavLink>
            ))}
            {!session && <Link to="/login" onClick={() => setOpen(false)} className="type-nav-link rounded-md px-2 py-2.5 text-ink">Sign in</Link>}
            {session ? (
              <>
                <Link to={workspaceHome()} onClick={() => setOpen(false)} className="type-nav-link rounded-md px-2 py-2.5 text-ink">My workspace</Link>
                <button type="button" onClick={() => { logout(); setOpen(false); }} className="type-nav-link rounded-md px-2 py-2.5 text-left text-zinc-500">Sign out</button>
              </>
            ) : (
              <Link to="/signup" onClick={() => setOpen(false)} className="btn-primary mt-2 text-center">Sign up</Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}

/** Workspace-aware account menu: avatar + workspace name, dropdown on click. */
function AccountMenu({ displayName, workspaceLabel, workspaceHome, showReports, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onPointer = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account menu for ${displayName}`}
        className="flex items-center gap-2 rounded-md border border-transparent p-1.5 pr-2 transition-colors hover:border-border hover:bg-surface-muted"
      >
        <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-subtle text-xs font-medium-plus text-primary">
          {initialsFor(displayName)}
        </span>
        <span className="max-w-36 truncate text-sm font-medium-plus text-ink">{displayName}</span>
        <ChevronDown className={`h-4 w-4 text-zinc-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div role="menu" aria-label="Account" className="absolute right-0 z-50 mt-2 w-64 rounded-md border border-border bg-white p-2 shadow-card">
          <p className="type-caption px-3 pb-1 pt-2 text-zinc-400">{workspaceLabel}</p>
          <Link to={workspaceHome} onClick={() => setOpen(false)} role="menuitem" className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium-plus text-ink hover:bg-surface-muted">
            <LayoutDashboard className="h-4 w-4 text-zinc-400" /> My workspace
          </Link>
          {showReports && (
            <Link to="/app/citizen/reports" onClick={() => setOpen(false)} role="menuitem" className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium-plus text-ink hover:bg-surface-muted">
              <FolderOpen className="h-4 w-4 text-zinc-400" /> My reports
            </Link>
          )}
          <div className="my-1 border-t border-border" />
          <button type="button" onClick={() => { setOpen(false); onLogout(); }} role="menuitem" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium-plus text-zinc-500 hover:bg-surface-muted hover:text-ink">
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
