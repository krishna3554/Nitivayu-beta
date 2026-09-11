import { useEffect, useState } from 'react';
import { getMetaConfig } from '../services/api';

// plan4: single source of truth for pipeline constants the UI used to
// hardcode (SLA windows, routing weights, districts, milestone structure).
// Fetched once per page load and shared; every consumer falls back to the
// previous hardcoded values when the API is unreachable.

const FALLBACK = {
  officer_sla_hours: 72,
  university_sla_hours: 168,
  score_weights: { theme: 0.4, semantic: 0.3, capacity: 0.2, geo: 0.1 },
  categories: [],
  languages: ['hindi', 'hinglish', 'english'],
  districts: [],
  max_upload_mb: 5,
  milestone_structure: [
    { num: 1, code: 'M1', title: 'Feasibility Study' },
    { num: 2, code: 'M2', title: 'Prototype Design' },
    { num: 3, code: 'M3', title: 'Field Validation' },
  ],
};

let cached = null;
let inflight = null;

export function fetchMetaConfig() {
  if (cached) return Promise.resolve(cached);
  if (!inflight) {
    inflight = getMetaConfig()
      .then(({ data }) => { cached = { ...FALLBACK, ...data }; return cached; })
      .catch(() => { cached = FALLBACK; return cached; })
      .finally(() => { inflight = null; });
  }
  return inflight;
}

export function useMetaConfig() {
  const [config, setConfig] = useState(cached || FALLBACK);
  const [ready, setReady] = useState(Boolean(cached));
  useEffect(() => {
    let live = true;
    fetchMetaConfig().then((c) => { if (live) { setConfig(c); setReady(true); } });
    return () => { live = false; };
  }, []);
  return { config, ready };
}

export function milestoneLabel(config, num) {
  const entry = (config?.milestone_structure || []).find((m) => m.num === num);
  return entry ? `${entry.code} ${entry.title}` : `M${num}`;
}
