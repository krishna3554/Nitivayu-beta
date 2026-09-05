import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useInViewOnce, useReducedMotion } from '../../lib/motion';

const COUNT = 14;
const COLORS = ['#6720FF', '#818CF8', '#F59E0B', '#6720FF', '#A78BFA', '#F59E0B'];

/** Deterministic scatter vectors — no Math.random in render. */
function vector(i) {
  const angle = (i / COUNT) * Math.PI * 2 + (i % 3) * 0.22;
  const dist = 46 + ((i * 37) % 40);
  return {
    tx: `${(Math.cos(angle) * dist).toFixed(1)}px`,
    ty: `${(Math.sin(angle) * dist).toFixed(1)}px`,
    size: 3 + ((i * 13) % 3),
    color: COLORS[i % COLORS.length],
    line: i % 4 === 3,
  };
}

/**
 * <MilestoneBurst> — one reusable firework micro-scatter for REAL
 * milestones only: report-submission success, milestone verified,
 * pledge confirmed. Fires once when first visible, settles, unmounts.
 * Never on hover, buttons, or minor-action toasts. Renders nothing
 * under prefers-reduced-motion.
 */
export default function MilestoneBurst({ className = '' }) {
  const ref = useRef(null);
  const seen = useInViewOnce(ref, 0.5);
  const reduced = useReducedMotion();
  const [settled, setSettled] = useState(false);
  const parts = useMemo(() => Array.from({ length: COUNT }, (_, i) => vector(i)), []);

  useEffect(() => {
    if (!seen || reduced) return;
    const t = setTimeout(() => setSettled(true), 750);
    return () => clearTimeout(t);
  }, [seen, reduced]);

  if (reduced || settled) return null;

  return (
    <div ref={ref} aria-hidden className={`burst-layer ${className}`}>
      {seen &&
        parts.map((p, i) =>
          p.line ? (
            <span
              key={i}
              className="burst-particle"
              style={{
                width: 14,
                height: 2,
                background: p.color,
                ['--tx']: p.tx,
                ['--ty']: p.ty,
              }}
            />
          ) : (
            <span
              key={i}
              className="burst-particle"
              style={{
                width: p.size,
                height: p.size,
                background: p.color,
                ['--tx']: p.tx,
                ['--ty']: p.ty,
              }}
            />
          ),
        )}
    </div>
  );
}
