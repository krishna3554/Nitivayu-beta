import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import BackgroundGrid from './BackgroundGrid';

const ACCENTS = {
  citizen: 'bg-emerald-500',
  officer: 'bg-primary',
  university: 'bg-academic',
  corporate: 'bg-csr',
  admin: 'bg-ink',
};

const TITLES = {
  citizen: 'Citizen App',
  officer: 'Officer Console',
  university: 'University Workspace',
  corporate: 'Corporate Workspace',
  admin: 'Admin Control Plane',
};

/**
 * AppShell — workspace-aware sidebar + topbar + content slot.
 * Each workspace renders ONLY its own nav; nothing disabled/hidden.
 */
export default function AppShell({ workspace = 'citizen', items = [], orgLabel, children, actions }) {
  const [open, setOpen] = useState(false);
  const [noticeOpen, setNoticeOpen] = useState(true);
  const location = useLocation();

  // Workspace notice dismisses itself — it must never squat in the sidebar.
  useEffect(() => {
    if (!noticeOpen) return;
    const t = setTimeout(() => setNoticeOpen(false), 8000);
    return () => clearTimeout(t);
  }, [noticeOpen]);

  // Exactly one nav item is active at a time. Index items (end:true) match
  // exactly; section items match themselves plus their children.
  const isActive = (item) => item.end
    ? location.pathname === item.to
    : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
  return (
    <div className="mx-auto flex min-h-[calc(100vh-73px)] w-full max-w-content flex-col md:flex-row">
      {/* Mobile bar */}
      <div className="flex items-center justify-between border-b border-border bg-white px-4 py-3 md:hidden">
        <p className="type-label-sm flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${ACCENTS[workspace] || 'bg-primary'}`} aria-hidden />
          {TITLES[workspace] || workspace}
        </p>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="rounded-md border border-border p-2"
          aria-label={open ? 'Close workspace menu' : 'Open workspace menu'}
        >
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
      </div>

      {/* Sidebar — pinned while main content scrolls (desktop) */}
      <aside className={`${open ? 'block' : 'hidden'} w-full shrink-0 border-b border-border bg-white p-4 md:sticky md:top-[73px] md:block md:max-h-[calc(100vh-73px)] md:w-64 md:self-start md:overflow-y-auto md:border-b-0 md:border-r`}>
        <div className="mb-4 hidden px-2 md:block">
          <p className="type-caption text-primary">{TITLES[workspace] || workspace}</p>
          {orgLabel && <p className="type-body-sm mt-1 text-zinc-500">{orgLabel}</p>}
        </div>
        <nav className="space-y-1" aria-label={`${workspace} workspace`}>
          {items.map((item) => {
            const active = isActive(item);
            const Icon = item.icon;
            return (
              <Link
                key={item.to + item.label}
                to={item.to}
                onClick={() => setOpen(false)}
                className={`flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium-plus transition-colors ${
                  active ? 'bg-primary-subtle text-primary' : 'text-ink-secondary hover:bg-surface-muted'
                }`}
              >
                <span className="flex items-center gap-2">
                  {Icon && <Icon className="h-4 w-4" />}
                  {item.label}
                </span>
                {item.badge != null && item.badge !== '' && (
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 text-xs font-medium-plus text-ink-secondary">{item.badge}</span>
                )}
              </Link>
            );
          })}
        </nav>
        {noticeOpen && (
          <div className="mt-6 hidden rounded-md border border-border bg-surface-muted p-3 md:block" role="status">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs leading-5 text-zinc-500">
                Signed in to the {TITLES[workspace] || workspace}. Other workspaces are not loaded in this session.
              </p>
              <button
                type="button"
                onClick={() => setNoticeOpen(false)}
                aria-label="Dismiss workspace notice"
                className="shrink-0 rounded-sm p-0.5 text-zinc-400 hover:text-ink"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* Content — quiet grid extends here for shell consistency;
          white cards sit above it, so table/card contrast is untouched */}
      <div className="relative min-w-0 flex-1 overflow-x-clip bg-grid">
        <BackgroundGrid />
        <div className="relative z-10">
        {(actions) && (
          <div className="flex items-center justify-end gap-3 border-b border-border bg-white px-4 py-3 md:px-6">
            {actions}
          </div>
        )}
        <div className="p-4 md:p-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
