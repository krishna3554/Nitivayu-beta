import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { loginUser } from '../services/api';

const AuthCtx = createContext(null);

// role (backend) → workspace (frontend route namespace)
export function roleToWorkspace(role) {
  switch (String(role || '').toLowerCase()) {
    case 'citizen': return 'citizen';
    case 'officer': return 'officer';
    case 'university': return 'university';
    case 'industry':
    case 'corporate':
    case 'csr': return 'corporate';
    case 'admin': return 'admin';
    default: return 'citizen';
  }
}

export function workspaceHome(workspace) {
  switch (workspace) {
    case 'citizen': return '/app/citizen';
    case 'officer': return '/app/officer';
    case 'university': return '/app/university';
    case 'corporate': return '/app/corporate';
    case 'admin': return '/app/admin';
    default: return '/app/citizen';
  }
}

function safeStorage() {
  try {
    localStorage.getItem('__probe');
    return localStorage;
  } catch { return null; }
}

function loadSession() {
  try {
    const store = safeStorage();
    if (!store) return null;
    const raw = store.getItem('nitivayu_session');
    if (!raw) {
      // Back-compat: legacy token-only storage. B3 drops the old officer
      // default — an orphan token is treated as citizen and re-resolved on
      // next login instead of opening the officer workspace.
      const legacy = store.getItem('nitivayu_token');
      return legacy ? { token: legacy, role: 'citizen', workspace: 'citizen', orgName: '', organizationId: null } : null;
    }
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || !parsed.token) return null;
    return parsed;
  } catch { return null; }
}

/**
 * Auth flow (nitivayu.md §4.3). Tokens live in memory (this provider) with a
 * localStorage mirror so a refresh keeps the workspace shell. When the backend
 * ships httpOnly-cookie refresh, only login()/logout() change — guards stay.
 */
export function AuthProvider({ children }) {
  const [session, setSession] = useState(loadSession);

  useEffect(() => {
    const store = safeStorage();
    if (!store) return;
    try {
      if (session) {
        store.setItem('nitivayu_session', JSON.stringify(session));
        if (session.token) store.setItem('nitivayu_token', session.token);
      } else {
        store.removeItem('nitivayu_session');
        store.removeItem('nitivayu_token');
      }
    } catch { /* private mode / quota */ }
  }, [session]);

  const login = useCallback(async ({ email, password }) => {
    const { data } = await loginUser({ email, password });
    const workspace = data.workspace_type ? roleToWorkspace(data.workspace_type) : roleToWorkspace(data.role);
    const next = {
      token: data.access_token,
      role: data.role || data.workspace_type || 'citizen',
      workspace,
      displayName: data.display_name || data.organization_name || '',
      orgName: data.organization_name || '',
      organizationId: data.organization_id || null,
    };
    setSession(next);
    return next;
  }, []);

  // Citizen OTP / invite flows land here in Phase 1/6; shape is identical.
  const loginWithSession = useCallback((next) => {
    const normalized = { ...next, workspace: next.workspace || roleToWorkspace(next.role), displayName: next.displayName || next.display_name || '' };
    delete normalized.display_name;
    setSession(normalized);
    return normalized;
  }, []);

  const logout = useCallback(() => setSession(null), []);

  const value = useMemo(() => ({
    session,
    login,
    loginWithSession,
    logout,
    workspaceHome: () => (session ? workspaceHome(session.workspace) : '/login'),
  }), [session, login, loginWithSession, logout]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/** Route guard: resolves workspace_type → correct app shell. */
export function RequireWorkspace({ allow = [], children }) {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  const workspace = session.workspace || roleToWorkspace(session.role);
  if (allow.length && !allow.includes(workspace) && !(workspace === 'admin' && allow.includes('preview'))) {
    return <Navigate to={workspaceHome(workspace)} replace />;
  }
  return children;
}
