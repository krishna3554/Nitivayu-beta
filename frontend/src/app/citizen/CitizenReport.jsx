import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Copy } from 'lucide-react';
import EvidenceComposer from '../../components/ui/EvidenceComposer';
import { submitComplaint } from '../../services/api';

function rememberReport(token, title) {
  try {
    const list = JSON.parse(localStorage.getItem('nitivayu_my_reports') || '[]');
    if (!list.some((r) => r.token === token)) {
      list.unshift({ token, title: (title || '').slice(0, 80), at: new Date().toISOString() });
      localStorage.setItem('nitivayu_my_reports', JSON.stringify(list.slice(0, 50)));
    }
  } catch { /* ignore */ }
}

export default function CitizenReport() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(null);

  const submit = async ({ text, language, district, block, geo, photos, audioBlob }) => {
    setSubmitting(true); setError('');
    try {
      const payload = new FormData();
      payload.append('raw_text', text);
      payload.append('language_pref', language);
      payload.append('district', district);
      if (block) payload.append('block', block);
      if (geo && Number.isFinite(Number(geo.lat)) && Number.isFinite(Number(geo.lng))) {
        payload.append('geo_lat', String(geo.lat));
        payload.append('geo_lng', String(geo.lng));
      }
      // Current API accepts a single `photo`; extras ride along for the
      // Phase-4 media pipeline (object storage + async attach).
      photos.slice(0, 4).forEach((p, i) => payload.append(i === 0 ? 'photo' : `photo_${i + 1}`, p, p.name));
      if (audioBlob) payload.append('audio_note', audioBlob, 'audio-note.webm');
      const { data } = await submitComplaint(payload);
      rememberReport(data.tracking_token, text);
      try { localStorage.removeItem('nitivayu_composer_draft'); } catch {}
      setDone(data);
    } catch (err) {
      const status = err.response?.status;
      setError(status === 413 ? 'Your photos are too large even after compression. Remove one and try again.'
        : err.response?.data?.detail || 'We could not submit your report. Your draft is saved — try again in a moment.');
    } finally { setSubmitting(false); }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-xl">
        <div className="card p-8 text-center">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500 text-white" aria-hidden><CheckCircle2 className="h-7 w-7" /></span>
          <h1 className="mt-4 text-2xl font-medium-plus tracking-tight">Your report is in.</h1>
          <p className="type-body-md mt-2 text-zinc-500">It reaches an officer within 72 hours. Save your tracking token — it is your public receipt.</p>
          <div className="mt-6 flex items-center justify-between rounded-md border border-border bg-surface-muted p-4">
            <span className="font-mono text-lg font-bold tracking-wider">{done.tracking_token}</span>
            <button type="button" onClick={() => { try { navigator.clipboard.writeText(done.tracking_token); } catch {} }} className="rounded-md border border-border p-2 hover:bg-white" aria-label="Copy tracking token"><Copy className="h-4 w-4" /></button>
          </div>
          <button type="button" onClick={() => navigate(`/track/${done.tracking_token}`)} className="btn-primary mt-6 w-full">Track progress</button>
          <button type="button" onClick={() => setDone(null)} className="link-inline mt-3 !text-sm">File another report</button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="type-display-md !text-3xl text-ink">Report an issue</h1>
      <p className="type-body-md mt-2 text-zinc-500">Describe it in your own words. Photos, audio, and GPS help — but text plus district is always enough.</p>
      <div className="mt-5"><EvidenceComposer onSubmit={submit} submitting={submitting} serverError={error} /></div>
    </div>
  );
}
