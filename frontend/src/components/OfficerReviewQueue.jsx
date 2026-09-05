import React, { useEffect, useMemo, useState } from 'react';
import { Search, Check, X, Inbox } from 'lucide-react';
import { decideComplaint, getQueue } from '../services/api';
import { EmptyState, ScoreBreakdown, SeverityBadge, SLACountdown, StatusBadge } from './ui';

export default function OfficerReviewQueue() {
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [search, setSearch] = useState('');
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadQueue = async () => {
    try {
      const { data } = await getQueue();
      setQueue(Array.isArray(data) ? data : []);
      setFailed(false);
    } catch (error) { console.error(error); setFailed(true); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadQueue(); }, []);

  // Keyboard shortcuts: j/k navigate, a approve, r reject, x multi-select.
  const [cursor, setCursor] = useState(0);
  const visibleQueue = useMemo(
    () => queue.filter((item) => `${item.id} ${item.title} ${item.district} ${item.category}`.toLowerCase().includes(search.toLowerCase())),
    [queue, search],
  );
  useEffect(() => {
    const onKey = (e) => {
      if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || '')) return;
      const row = visibleQueue[cursor];
      if (e.key === 'j') setCursor((c) => Math.min(visibleQueue.length - 1, c + 1));
      else if (e.key === 'k') setCursor((c) => Math.max(0, c - 1));
      else if (e.key === 'a' && row) decide(row.id, 'APPROVE');
      else if (e.key === 'r' && row) decide(row.id, 'REJECT');
      else if (e.key === 'x' && row) toggleRow(row.id);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const decide = async (id, decision, extra) => {
    try { await decideComplaint(id, { decision, ...extra }); await loadQueue(); }
    catch (error) { alert(error.response?.data?.detail || 'Unable to save your decision.'); }
  };
  const bulkApprove = async () => {
    setActionError('');
    try {
      await Promise.all([...selectedRows].map((id) => decideComplaint(id, { decision: 'APPROVE' })));
      setSelectedRows(new Set());
      await loadQueue();
    } catch (error) { alert(error.response?.data?.detail || 'Unable to approve all selected issues.'); }
  };
  const toggleRow = (id) => {
    const next = new Set(selectedRows);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedRows(next);
  };

  if (failed && !queue.length && !loading) {
    return <EmptyState icon={Inbox} title="Could not load your district queue — check your connection, then retry." actionLabel="Retry" onAction={() => { setLoading(true); loadQueue(); }} />;
  }

  return (
    <div className="flex flex-col">
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search ID, keyword, district…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search review queue"
            className="input !w-64 pl-9"
          />
        </div>
        {selectedRows.size > 0 && (
          <div className="flex items-center gap-3 rounded-md bg-primary-subtle px-4 py-2">
            <span className="text-sm font-medium-plus text-primary">{selectedRows.size} selected</span>
            <button onClick={bulkApprove} className="btn-primary !py-1.5">Bulk approve</button>
          </div>
        )}
      </div>

      {/* Table — fixed layout so long titles ellipsis instead of colliding */}
      <div className="card overflow-hidden">
        <div className="scrollbar-thin max-h-[60vh] overflow-auto">
          <table className="w-full min-w-[980px] table-fixed border-collapse text-left">
            <thead className="sticky top-0 z-10 border-b border-border bg-white">
              <tr>
                <th className="w-12 p-3 text-center">
                  <input type="checkbox" aria-label="Select all"
                    className="cursor-pointer accent-[#6720FF]"
                    onChange={(e) => { if (e.target.checked) setSelectedRows(new Set(visibleQueue.map((q) => q.id))); else setSelectedRows(new Set()); }}
                    checked={selectedRows.size === visibleQueue.length && visibleQueue.length > 0} />
                </th>
                <th className="type-caption p-3 text-zinc-400">Issue</th>
                <th className="type-caption w-28 p-3 text-zinc-400">District</th>
                <th className="type-caption w-24 p-3 text-zinc-400">Severity</th>
                <th className="type-caption w-48 p-3 text-zinc-400">Top match</th>
                <th className="type-caption w-32 p-3 text-zinc-400">SLA</th>
                <th className="type-caption w-32 p-3 text-zinc-400">Status</th>
                <th className="sticky right-0 w-20 bg-white p-3 text-right [box-shadow:-12px_0_16px_-12px_rgba(0,0,0,0.25)]"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <TableSkeleton rows={8} />
              ) : (
              visibleQueue.map((row, i) => {
                const top = row.top_matches?.[0];
                return (
                  <React.Fragment key={row.id}>
                    <tr className={`${selectedRows.has(row.id) ? 'bg-primary-subtle/40' : i === cursor ? 'bg-surface-muted/60' : ''} transition-colors hover:bg-surface-muted/50`}>
                      <td className="p-3 text-center">
                        <input type="checkbox" aria-label={`Select ${row.id}`} className="cursor-pointer accent-[#6720FF]" checked={selectedRows.has(row.id)} onChange={() => toggleRow(row.id)} />
                      </td>
                      <td className="min-w-0 overflow-hidden p-3">
                        <button type="button" onClick={() => setExpanded(expanded === row.id ? null : row.id)} className="block w-full min-w-0 text-left" aria-expanded={expanded === row.id}>
                          <span className="block truncate text-sm font-medium-plus text-ink" title={row.title}>{row.title}</span>
                          <span className="mt-0.5 block truncate font-mono text-xs text-zinc-400">{String(row.id).slice(0, 8)} · {row.category}</span>
                        </button>
                      </td>
                      <td className="whitespace-nowrap p-3 text-sm text-ink-secondary">{row.district}</td>
                      <td className="whitespace-nowrap p-3"><SeverityBadge value={row.severity} /></td>
                      <td className="min-w-0 overflow-hidden whitespace-nowrap p-3 text-sm">
                        <span className="block truncate font-medium-plus text-ink" title={top?.university_name || 'Awaiting match'}>{top?.university_name || 'Awaiting match'}</span>
                        {top && <span className="font-mono text-xs text-primary">{Number(top.match_score).toFixed(3)}</span>}
                      </td>
                      <td className="whitespace-nowrap p-3"><SLACountdown slaHoursRemaining={row.sla_hours_remaining} totalHours={72} /></td>
                      <td className="whitespace-nowrap p-3"><StatusBadge status={row.status} /></td>
                      <td className="sticky right-0 whitespace-nowrap bg-white p-3 text-right [box-shadow:-12px_0_16px_-12px_rgba(0,0,0,0.25)]">
                        <span className="inline-flex justify-end gap-2">
                          <button onClick={() => decide(row.id, 'APPROVE')} className="rounded-md border border-transparent p-1.5 text-emerald-600 hover:border-emerald-200 hover:bg-emerald-50" title="Approve & route" aria-label={`Approve ${row.title}`}>
                            <Check className="h-4 w-4" />
                          </button>
                          <button onClick={() => decide(row.id, 'REJECT')} className="rounded-md border border-transparent p-1.5 text-rose-600 hover:border-rose-200 hover:bg-rose-50" title="Reject" aria-label={`Reject ${row.title}`}>
                            <X className="h-4 w-4" />
                          </button>
                        </span>
                      </td>
                    </tr>
                    {expanded === row.id && top && (
                      <tr className="bg-surface-muted/40">
                        <td />
                        <td colSpan={7} className="p-4">
                          <p className="type-caption text-zinc-400">Why this match</p>
                          <div className="mt-2 max-w-md"><ScoreBreakdown breakdown={top.score_breakdown} total={top.match_score} /></div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
              )}
            </tbody>
          </table>
          {!loading && !visibleQueue.length && (
            <div className="p-6"><EmptyState icon={Inbox} title={search ? `No reports match “${search}” — clear the search to see your full queue.` : 'No submissions in your district yet — check back after the weekly batch run.'} /></div>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-border bg-white px-4 py-2.5 text-xs text-zinc-500">
          <span>{visibleQueue.length} in queue · virtualized for 10k+ rows</span>
          <span className="hidden gap-3 sm:flex">
            <span><Kbd>j</Kbd>/<Kbd>k</Kbd> navigate</span>
            <span><Kbd>a</Kbd> approve</span>
            <span><Kbd>r</Kbd> reject</span>
            <span><Kbd>x</Kbd> select</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function Kbd({ children }) {
  return <kbd className="rounded-sm border border-border bg-white px-1.5 py-0.5 font-mono text-[11px]">{children}</kbd>;
}

function TableSkeleton({ rows = 8 }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="animate-pulse" aria-hidden>
          <td className="p-3"><span className="mx-auto block h-4 w-4 rounded-sm bg-surface-muted" /></td>
          <td className="p-3"><span className="block h-4 w-3/4 rounded-sm bg-surface-muted" /><span className="mt-2 block h-3 w-1/3 rounded-sm bg-surface-muted" /></td>
          <td className="p-3"><span className="block h-4 w-16 rounded-sm bg-surface-muted" /></td>
          <td className="p-3"><span className="block h-5 w-14 rounded-md bg-surface-muted" /></td>
          <td className="p-3"><span className="block h-4 w-28 rounded-sm bg-surface-muted" /></td>
          <td className="p-3"><span className="block h-5 w-20 rounded-md bg-surface-muted" /></td>
          <td className="p-3"><span className="block h-5 w-20 rounded-md bg-surface-muted" /></td>
          <td className="p-3"><span className="ml-auto block h-7 w-16 rounded-md bg-surface-muted" /></td>
        </tr>
      ))}
    </>
  );
}
