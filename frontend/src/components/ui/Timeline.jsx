import React from 'react';
import { Check } from 'lucide-react';

/**
 * Timeline — vertical stepper with states: done / active / pending.
 * Used by citizen tracker and milestone views.
 */
export default function Timeline({ steps = [], className = '' }) {
  return (
    <ol className={`space-y-0 ${className}`}>
      {steps.map((step, i) => {
        const state = step.state || 'pending';
        const last = i === steps.length - 1;
        return (
          <li key={step.id || step.label || i} className="relative flex gap-4 pb-6 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className={`absolute left-[13px] top-7 h-[calc(100%-20px)] w-px ${state === 'done' ? 'bg-emerald-500' : 'bg-border'}`}
              />
            )}
            <span
              className={
                state === 'done'
                  ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white'
                  : state === 'active'
                    ? 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-primary bg-primary-subtle text-primary'
                    : 'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-surface-muted text-zinc-400'
              }
            >
              {state === 'done' ? <Check className="h-3.5 w-3.5" /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={`text-sm font-medium-plus ${state === 'pending' ? 'text-zinc-500' : 'text-ink'}`}>{step.label}</p>
              {step.sub && <p className="mt-0.5 text-xs text-zinc-500">{step.sub}</p>}
              {step.time && <p className="mt-0.5 font-mono text-xs text-zinc-400">{step.time}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
