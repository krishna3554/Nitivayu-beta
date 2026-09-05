import { useEffect, useRef, useState } from 'react';

/** True when the OS asks for reduced motion. All ambient effects obey it. */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!mq) return;
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);
  return reduced;
}

/** IntersectionObserver that fires exactly once. Falls back to visible. */
export function useInViewOnce(ref, threshold = 0.4) {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (seen) return;
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen, ref]);
  return seen;
}

/**
 * Section-local parallax: drifts the attached background layer at a
 * fraction of scroll speed via transform only (rAF-throttled, passive).
 * Returns a ref to attach to the *background layer*; pass the section
 * element as `sectionRef`. No-op under reduced motion.
 */
export function useParallaxLayer(sectionRef, rate = 0.12) {
  const layerRef = useRef(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const section = sectionRef.current;
      const layer = layerRef.current;
      if (!section || !layer) return;
      const r = section.getBoundingClientRect();
      const offset = (r.top + r.height / 2 - window.innerHeight / 2) * rate;
      layer.style.transform = `translate3d(0, ${offset.toFixed(1)}px, 0)`;
    };
    const schedule = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [sectionRef, rate, reduced]);
  return layerRef;
}
