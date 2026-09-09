import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import { EmptyState, StatusBadge } from '../../components/ui';
import { claimReport, getComplaint, getMyReports } from '../../services/api';
import { useAuth } from '../../lib/auth';

function loadLocal() {
  try { return JSON.parse(localStorage.getItem('nitivayu_my_reports') || '[]') || []; } catch { return []; }
}

export default function CitizenMyReports() {
  const { session } = useAuth();
  const [account, setAccount] = useState(null); // null = anonymous, [] = signed in, empty
  const [local, setLocal] = useState(loadLocal);
  const [statuses, setStatuses] = useState({});
  const [claimToken, setClaimToken] = useState('');
  const [claimMsg, setClaimMsg] = useState('');

  // Account-scoped history (works on any device once signed in).
  useEffect(() => {
    let live = true;
    if (!session?.token) { setAccount(null); return () => { live = false; }; }
    getMyReports()
      .then(({ data }) => { if (live) setAccount(data?.items || []); })
      .catch(() => { if (live) setAccount([]); });
    return () => { live = false; };
  }, [session?.token]);

  // Anonymous fallback: resolve the device-local tokens one by one.
  useEffect(() => {
    let live = true;
    local.slice(0, 20).forEach(async (r) => {
      try {
        const { data } = await getComplaint(r.token);
        if (live) setStatuses((s) => ({ ...s, [r.token]: data.status }));
      } catch { /* tracker will explain on open */ }
    });
    return () => { live = false; };
  }, [local]);

  const removeLocal = (token) => {
    const next = local.filter((r) => r.token !== token);
    setLocal(next);
    try { localStorage.setItem('nitivayu_my_reports', JSON.stringify(next)); } catch {}
  };

  const claim = async (e) => {
    e.preventDefault();
    setClaimMsg('');
    const token = claimToken.trim();
    if (!token) return;
    try {
      await claimReport(token);
      setClaimToken('');
      setClaimMsg('Linked — the report now appears in your account list above.');
      const { data } = await getMyReports();
      setAccount(data?.items || []);
    } catch (err) { setClaimMsg(err.response?.data?.detail || 'Could not link that token.'); }
  };

  const claimedTokens = new Set((account || []).map((r) => r.tracking_token));
  const unclaimedLocal = local.filter((r) => !claimedTokens.has(r.token));

  if (!session?.token && !local.length) {
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="type-display-md !text-3xl">My reports</h1>
        <div className="mt-5"><EmptyState icon={FolderOpen} title="You have no reports on this device yet — describe your first issue and it will appear here." actionLabel="Report an issue" actionTo="/app/citizen/report" /></div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="type-display-md !text-3xl">My reports</h1>
      {session?.token ? (
        <p className="type-body-md mt-2 text-zinc-500">Synced to your account — visible on any device you sign in from.</p>
      ) : (
        <p className="type-body-md mt-2 text-zinc-500">Saved on this device. <Link to="/login" className="link-inline !text-sm">Sign in</Link> to sync them to your account.</p>
      )}

      {(account || []).length > 0 && (
        <ul className="mt-5 space-y-3">
          {account.map((r) => (
            <li key={r.tracking_token} className="card flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <Link to={`/track/${r.tracking_token}`} className="link-inline !text-sm font-medium-plus">{r.tracking_token}</Link>
                {r.title && <p className="mt-1 truncate text-sm text-zinc-500">{r.title}</p>}
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusBadge status={r.status} />
                  {r.matched_university && <span className="text-xs text-zinc-500">{r.matched_university}</span>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {session?.token && (
        <form onSubmit={claim} className="card mt-5 flex flex-wrap items-center gap-2 p-4">
          <input
            value={claimToken}
            onChange={(e) => setClaimToken(e.target.value)}
            placeholder="Have a token from another device? Paste it to link"
            className="input min-w-0 flex-1 font-mono !text-sm"
            aria-label="Tracking token to link"
          />
          <button type="submit" className="btn-secondary !py-2">Link report</button>
          {claimMsg && <p className="w-full text-sm text-zinc-500">{claimMsg}</p>}
        </form>
      )}

      {unclaimedLocal.length > 0 && (
        <>
          <h2 className="type-label-sm mt-6 text-zinc-500">On this device only</h2>
          <ul className="mt-3 space-y-3">
            {unclaimedLocal.map((r) => (
              <li key={r.token} className="card flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <Link to={`/track/${r.token}`} className="link-inline !text-sm font-medium-plus">{r.token}</Link>
                  {r.title && <p className="mt-1 truncate text-sm text-zinc-500">{r.title}</p>}
                  <div className="mt-2">{statuses[r.token] ? <StatusBadge status={statuses[r.token]} /> : <span className="text-xs text-zinc-400">Checking status…</span>}</div>
                </div>
                <button type="button" onClick={() => removeLocal(r.token)} className="shrink-0 text-xs text-zinc-400 hover:text-ink">Remove</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
