import React from 'react';
import AmbientGlow from './AmbientGlow';

/**
 * MomentGlow — the reserved "this moment matters" glow (see --glow-accent),
 * now with a slow ambient drift (static under prefers-reduced-motion).
 * Use in exactly three places: the landing Live Pipeline card, the citizen
 * submit-success state, and verified/confirmed states. Nowhere else.
 * Static, behind content, never intercepts clicks.
 */
export default function MomentGlow({ children, className = '' }) {
  return (
    <div className={`relative ${className}`}>
      <AmbientGlow />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
