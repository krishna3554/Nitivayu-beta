import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import { EmptyState, StatusBadge } from '../../components/ui';
import { getComplaint } from '../../services/api';

function loadMine() {
  try { return JSON.parse(localStorage.getItem('nitivayu_my_reports') || '[]') || []; } catch { return []; }
}

export default function CitizenMyReports() {
  const [mine, setMine] = useState(loadMine);
  const [statuses, setStatuses] = useState({});

  useEffect(() => {
    let live = true;
    mine.slice(0, 20).forEach(async (r) => {
      try {
        const { data } = await getComplaint(r.token);
        if (live) setStatuses((s) => ({ ...s, [r.token]: data.status }));
      } catch { /* tracker will explain on open */ }
    });
    return () => { live = false; };
  }, [mine]);

  const remove = (token) => {
    const next = mine.filter((r) => r.token !== token);
    setMine(next);
    try { localStorage.setItem('nitivayu_my_reports', JSON.stringify(next)); } catch {}
  };

  if (!mine.length) {
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
      <p className="type-body-md mt-2 text-zinc-500">Saved on this device. Open any report for its live timeline.</p>
      <ul className="mt-5 space-y-3">
        {mine.map((r) => (
          <li key={r.token} className="card flex items-center justify-between gap-4 p-4">
            <div className="min-w-0">
              <Link to={`/track/${r.token}`} className="link-inline !text-sm font-medium-plus">{r.token}</Link>
              {r.title && <p className="mt-1 truncate text-sm text-zinc-500">{r.title}</p>}
              <div className="mt-2">{statuses[r.token] ? <StatusBadge status={statuses[r.token]} /> : <span className="text-xs text-zinc-400">Checking status…</span>}</div>
            </div>
            <button type="button" onClick={() => remove(r.token)} className="shrink-0 text-xs text-zinc-400 hover:text-ink">Remove</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
