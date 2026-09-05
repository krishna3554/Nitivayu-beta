import React from 'react';

/** SeverityBadge — 1–5 with color ramp. Scoped to severity display only. */
export default function SeverityBadge({ value, className = '' }) {
  const n = Number(value);
  const label = Number.isFinite(n) ? `${Math.min(5, Math.max(1, Math.round(n)))}/5` : '—';
  let tone = 'bg-surface-muted text-ink-secondary';
  if (n >= 5) tone = 'bg-rose-600 text-white';
  else if (n >= 4) tone = 'bg-rose-50 text-rose-700 border border-rose-200';
  else if (n >= 3) tone = 'bg-amber-50 text-amber-700 border border-amber-200';
  return (
    <span
      title={n >= 4 ? 'High severity — prioritized for officer review' : `Severity ${label}`}
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium-plus ${tone} ${className}`}
    >
      <span aria-hidden className="tracking-micro">S{Number.isFinite(n) ? Math.min(5, Math.max(1, Math.round(n))) : '–'}</span>
      <span className="opacity-70">{label}</span>
    </span>
  );
}
