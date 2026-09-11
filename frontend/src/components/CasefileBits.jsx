import React, { useEffect, useState } from 'react';
import { getMediaBlob } from '../services/api';

/** Authenticated media: <img>/<audio> can't send JWT headers, so fetch as a blob. */
export function useMediaUrl(assetId) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!assetId) return;
    let live = true;
    let objectUrl = null;
    getMediaBlob(assetId)
      .then(({ data }) => {
        if (!live) return;
        objectUrl = URL.createObjectURL(data);
        setUrl(objectUrl);
      })
      .catch(() => { if (live) setUrl(null); });
    return () => { live = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [assetId]);
  return url;
}

/** Photo gallery with lightbox (keyboard: Esc close, ←/→ step). */
export function MediaGallery({ assets = [] }) {
  const photos = assets.filter((a) => a.kind === 'photo');
  const [index, setIndex] = useState(null);

  useEffect(() => {
    if (index === null) return;
    const onKey = (e) => {
      if (e.key === 'Escape') setIndex(null);
      if (e.key === 'ArrowRight') setIndex((i) => (i + 1) % photos.length);
      if (e.key === 'ArrowLeft') setIndex((i) => (i - 1 + photos.length) % photos.length);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [index, photos.length]);

  if (!photos.length) return null;
  return (
    <div>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        {photos.map((p, i) => (
          <GalleryThumb key={p.asset_id} assetId={p.asset_id} index={i} onOpen={() => setIndex(i)} />
        ))}
      </div>
      {index !== null && (
        <Lightbox
          assetId={photos[index].asset_id}
          position={`${index + 1} / ${photos.length}`}
          onClose={() => setIndex(null)}
          onPrev={() => setIndex((index - 1 + photos.length) % photos.length)}
          onNext={() => setIndex((index + 1) % photos.length)}
        />
      )}
    </div>
  );
}

function GalleryThumb({ assetId, index, onOpen }) {
  const url = useMediaUrl(assetId);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Open evidence photo ${index + 1}`}
      className="aspect-square overflow-hidden rounded-md border border-border bg-surface-muted"
    >
      {url ? <img src={url} alt={`Evidence photo ${index + 1}`} className="h-full w-full object-cover hover:opacity-90" /> : (
        <span className="flex h-full w-full items-center justify-center text-xs text-zinc-400">Loading…</span>
      )}
    </button>
  );
}

function Lightbox({ assetId, position, onClose, onPrev, onNext }) {
  const url = useMediaUrl(assetId);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Evidence photo viewer" onClick={onClose}>
      <div className="relative max-h-full max-w-3xl" onClick={(e) => e.stopPropagation()}>
        {url ? <img src={url} alt="Evidence photo, enlarged" className="max-h-[80vh] rounded-md object-contain" /> : (
          <p className="rounded-md bg-white p-8 text-sm text-zinc-500">Loading photo…</p>
        )}
        <p className="mt-2 text-center font-mono text-xs text-white/70">{position}</p>
        <div className="mt-3 flex justify-center gap-2">
          <button type="button" onClick={onPrev} aria-label="Previous photo" className="rounded-md bg-white px-4 py-2 text-sm font-medium-plus">‹ Prev</button>
          <button type="button" onClick={onClose} className="rounded-md bg-white px-4 py-2 text-sm font-medium-plus">Close</button>
          <button type="button" onClick={onNext} aria-label="Next photo" className="rounded-md bg-white px-4 py-2 text-sm font-medium-plus">Next ›</button>
        </div>
      </div>
    </div>
  );
}

/** Inline audio player for an audio asset. */
export function AudioPlayer({ asset }) {
  const url = useMediaUrl(asset?.asset_id);
  if (!asset) return null;
  return (
    <div className="rounded-md border border-border bg-surface-muted p-3">
      {url ? (
        <audio src={url} controls className="h-9 w-full" aria-label="Citizen audio note" />
      ) : (
        <p className="text-sm text-zinc-500">Loading audio note…</p>
      )}
      {asset.transcript ? (
        <div className="mt-2 rounded-sm border border-border bg-white p-3">
          <p className="type-caption text-zinc-400">Transcript</p>
          <p className="type-body-sm mt-1 text-ink-secondary">{asset.transcript}</p>
        </div>
      ) : (
        <p className="type-body-sm mt-2 text-zinc-400">No transcript yet — triage used the written description.</p>
      )}
    </div>
  );
}

/** Location block with GPS-vs-manual provenance. */
export function LocationBlock({ submission }) {
  if (!submission) return null;
  const source = submission.geo_source || 'district';
  const sourceLabel = source === 'gps'
    ? 'GPS auto-detected on the citizen’s device'
    : source === 'manual'
      ? 'Manually entered / corrected by the citizen'
      : 'District only — no coordinates attached';
  return (
    <div className="rounded-md border border-border bg-surface-muted p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="tag-chip !text-xs">{sourceLabel}</span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2">
        <div><dt className="text-xs text-zinc-500">Latitude</dt><dd className="font-mono">{submission.geo_lat ?? '—'}</dd></div>
        <div><dt className="text-xs text-zinc-500">Longitude</dt><dd className="font-mono">{submission.geo_lng ?? '—'}</dd></div>
        <div><dt className="text-xs text-zinc-500">District</dt><dd>{submission.district || '—'}</dd></div>
        <div><dt className="text-xs text-zinc-500">Block / area</dt><dd>{submission.block || '—'}</dd></div>
      </dl>
    </div>
  );
}
