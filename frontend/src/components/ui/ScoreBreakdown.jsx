import React from 'react';

/**
 * ScoreBreakdown — 4-factor match explanation as small bars.
 * score = 0.4*theme + 0.3*semantic + 0.2*capacity + 0.1*geo (worker impl).
 */
const FACTORS = [
  { key: 'theme', label: 'Theme', weight: '0.4' },
  { key: 'semantic', label: 'Semantic', weight: '0.3' },
  { key: 'capacity', label: 'Capacity', weight: '0.2' },
  { key: 'geo', label: 'Proximity', weight: '0.1' },
];

export default function ScoreBreakdown({ breakdown = {}, total, compact = false }) {
  return (
    <div className={compact ? 'space-y-1.5' : 'space-y-2'}>
      {FACTORS.map(({ key, label, weight }) => {
        const v = Number(breakdown[key]);
        const pct = Number.isFinite(v) ? Math.round(Math.min(1, Math.max(0, v)) * 100) : null;
        return (
          <div key={key} className="flex items-center gap-2">
            <span className="w-20 shrink-0 text-xs text-zinc-500">{label} <span className="text-zinc-400">×{weight}</span></span>
            <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-surface-muted">
              <span className="block h-full rounded-full bg-primary" style={{ width: `${pct ?? 0}%` }} />
            </span>
            <span className="w-9 shrink-0 text-right font-mono text-xs text-ink-secondary">{pct ?? '–'}</span>
          </div>
        );
      })}
      {Number.isFinite(Number(total)) && (
        <p className="pt-1 font-mono text-xs text-ink-secondary">match {Number(total).toFixed(3)}</p>
      )}
    </div>
  );
}
