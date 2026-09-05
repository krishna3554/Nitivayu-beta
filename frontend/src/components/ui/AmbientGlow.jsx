import React from 'react';

/**
 * <AmbientGlow> — the reserved 340px moment glow on its 16s loop
 * (±6% drift, 1.12x at midpoint; transform-only, GPU-friendly).
 * Static centered glow under prefers-reduced-motion (see CSS guard).
 */
export default function AmbientGlow({ className = '' }) {
  return <span aria-hidden className={`glow-accent glow-loop ${className}`} />;
}
