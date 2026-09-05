import React from 'react';

const CORNERS = [
  'left-4 top-4 border-l-2 border-t-2',
  'right-4 top-4 border-r-2 border-t-2',
  'bottom-4 left-4 border-b-2 border-l-2',
  'bottom-4 right-4 border-b-2 border-r-2',
];

/**
 * SectionCorners — echoes the pipeline-card bracket motif, very faintly,
 * at the outer corners of major page sections (never on cards).
 * Parent section must be `relative`. Static, pointer-events none.
 */
export default function SectionCorners({ className = '' }) {
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 z-0 ${className}`}>
      {CORNERS.map((pos) => (
        <span key={pos} className={`corner-mark ${pos}`} />
      ))}
    </div>
  );
}
