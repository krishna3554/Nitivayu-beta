import React, { useEffect, useState } from 'react';
import { Clock, AlertTriangle } from 'lucide-react';

function diffParts(deadline) {
  const ms = new Date(deadline).getTime() - Date.now();
  if (!Number.isFinite(ms)) return null;
  if (ms <= 0) return { overdue: true, h: 0, m: 0 };
  return { overdue: false, h: Math.floor(ms / 3600000), m: Math.floor((ms % 3600000) / 60000) };
}

/**
 * SLACountdown — deadline → live countdown, warning state at <20% remaining.
 * Provide totalHours so the 20% threshold is meaningful (72h officer, 168h university).
 */
export default function SLACountdown({ deadline, totalHours = 72, slaHoursRemaining, className = '' }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((v) => v + 1), 30000);
    return () => clearInterval(t);
  }, []);

  let label = '—';
  let warning = false;
  let overdue = false;

  if (deadline) {
    const d = diffParts(deadline);
    if (d) {
      overdue = d.overdue;
      label = d.overdue ? 'Overdue' : d.h >= 24 ? `${Math.floor(d.h / 24)}d ${d.h % 24}h left` : `${d.h}h ${d.m}m left`;
      const remainingMs = new Date(deadline).getTime() - Date.now();
      warning = !d.overdue && remainingMs < totalHours * 3600000 * 0.2;
    }
  } else if (Number.isFinite(Number(slaHoursRemaining))) {
    const h = Number(slaHoursRemaining);
    overdue = h <= 0;
    label = h <= 0 ? 'Overdue' : `${Math.round(h)}h left`;
    warning = h > 0 && h < totalHours * 0.2;
  }

  const tone = overdue || warning
    ? 'bg-rose-50 text-rose-700 border-rose-200'
    : 'bg-surface-muted text-ink-secondary border-transparent';

  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium-plus ${tone} ${className}`}>
      {overdue || warning ? <AlertTriangle className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
      {label}
    </span>
  );
}
