import React, { forwardRef } from 'react';

/**
 * <BackgroundGrid> — wash + dot-grid as an independent, movable background
 * layer (a plain `.bg-grid` class can't parallax on its own).
 *
 * Usage:
 *   const sectionRef = useRef(null);
 *   const gridRef = useParallaxLayer(sectionRef); // from lib/motion
 *   <section ref={sectionRef} className="relative overflow-clip ...">
 *     <BackgroundGrid ref={gridRef} />
 *     <div className="relative z-10 ...">content</div>
 *   </section>
 *
 * Static, behind content (z-0), never intercepts clicks. Under
 * prefers-reduced-motion the parallax hook is a no-op and the layer
 * sits still.
 */
const BackgroundGrid = forwardRef(function BackgroundGrid({ className = '' }, ref) {
  return <div ref={ref} aria-hidden className={`bg-grid-layer ${className}`} />;
});

export default BackgroundGrid;
