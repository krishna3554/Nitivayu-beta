import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, ImagePlus, Mic, MapPin, X, Loader2, Navigation } from 'lucide-react';

const MAX_CHARS = 5000;
const MAX_AUDIO_SECONDS = 60;
const MAX_IMAGE_EDGE = 1600;

export const JHARKHAND_DISTRICTS = [
  'Ranchi', 'Dhanbad', 'Bokaro', 'East Singhbhum', 'West Singhbhum', 'Seraikela-Kharsawan',
  'Palamu', 'Garhwa', 'Latehar', 'Chatra', 'Hazaribagh', 'Koderma', 'Giridih', 'Deoghar',
  'Dumka', 'Godda', 'Sahebganj', 'Pakur', 'Jamtara', 'Lohardaga', 'Gumla', 'Simdega',
  'Khunti', 'Ramgarh',
];

/** Downscale to max 1600px longest edge, re-encode WebP (~150–300KB typical). */
export async function compressImage(file) {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(bitmap.width, bitmap.height));
    if (scale >= 1 && (file.type === 'image/webp' || file.size < 350 * 1024)) return file;
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/webp', 0.82));
    bitmap.close?.();
    return blob ? new File([blob], file.name.replace(/\.\w+$/, '') + '.webp', { type: 'image/webp' }) : file;
  } catch {
    return file; // never block submit on compression failure
  }
}

function useDraftPersistence(key, value) {
  useEffect(() => {
    try {
      const { photos, audioBlob, ...rest } = value; // media blobs stay in memory only
      localStorage.setItem(key, JSON.stringify(rest));
    } catch { /* quota / private mode — ignore */ }
  }, [key, value]);
}

export function loadDraft(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

/**
 * EvidenceComposer — single-screen multimodal intake (§3, nitivayu.md).
 * Text always visible; photo / camera / audio / location are inline chips.
 * Every capture surface degrades gracefully — the form never hard-blocks
 * on a denied permission. Mobile-first, screen-reader labelled.
 */
export default function EvidenceComposer({ onSubmit, submitting, serverError }) {
  const saved = React.useMemo(() => loadDraft('nitivayu_composer_draft'), []);
  const [text, setText] = useState(saved?.text || '');
  const [language, setLanguage] = useState(saved?.language || 'hinglish');
  const [district, setDistrict] = useState(saved?.district || 'Ranchi');
  const [block, setBlock] = useState(saved?.block || '');
  const [photos, setPhotos] = useState([]);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [geo, setGeo] = useState(saved?.geo || null);
  const [geoStatus, setGeoStatus] = useState('idle'); // idle|locating|ok|denied|unsupported
  const [sheet, setSheet] = useState(null); // photo|camera|audio|location
  const [recording, setRecording] = useState(false);
  const [recSecs, setRecSecs] = useState(0);
  const [compressing, setCompressing] = useState(null); // {done,total} while photos compress

  const fileRef = useRef(null);
  const cameraFileRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const recTimerRef = useRef(null);
  const chunksRef = useRef([]);

  const canRecordAudio = typeof window !== 'undefined' && typeof window.MediaRecorder !== 'undefined';
  const canCamera = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;

  useDraftPersistence('nitivayu_composer_draft', { text, language, district, block, geo });

  // Auto-detect GPS on open (explicit permission prompt owned by the browser).
  useEffect(() => {
    if (!('geolocation' in navigator)) { setGeoStatus('unsupported'); return; }
    setGeoStatus('locating');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeo({ lat: Number(pos.coords.latitude.toFixed(6)), lng: Number(pos.coords.longitude.toFixed(6)) });
        setGeoStatus('ok');
      },
      () => setGeoStatus('denied'), // fallback: district/block dropdown always works
      { timeout: 8000, maximumAge: 60000 },
    );
  }, []);

  const detectGeo = useCallback(() => {
    if (!('geolocation' in navigator)) { setGeoStatus('unsupported'); return; }
    setGeoStatus('locating');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeo({ lat: Number(pos.coords.latitude.toFixed(6)), lng: Number(pos.coords.longitude.toFixed(6)) });
        setGeoStatus('ok');
      },
      () => setGeoStatus('denied'),
      { timeout: 8000 },
    );
  }, []);

  // ——— photos ———
  const addFiles = async (files) => {
    const list = Array.from(files || []).filter((f) => f.type.startsWith('image/'));
    if (!list.length) return;
    const batch = [...list].slice(0, 4 - photos.length);
    setCompressing({ done: 0, total: batch.length });
    const compressed = [];
    for (let i = 0; i < batch.length; i++) {
      compressed.push(await compressImage(batch[i]));
      setCompressing({ done: i + 1, total: batch.length });
    }
    setPhotos((prev) => [...prev, ...compressed].slice(0, 4));
    setCompressing(null);
    setSheet(null);
  };

  // ——— in-browser camera ———
  const openCamera = async () => {
    setSheet('camera');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => {}); }
    } catch {
      // Permission denied / no camera → fall back to file upload silently.
      setSheet('photo');
    }
  };
  const stopCamera = () => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; };
  useEffect(() => () => { stopCamera(); mediaRecorderRef.current?.state !== 'inactive' && mediaRecorderRef.current?.stop(); clearInterval(recTimerRef.current); }, []);

  const captureFrame = () => {
    const video = videoRef.current;
    if (!video?.videoWidth) return;
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) setPhotos((prev) => [...prev, new File([blob], `capture-${Date.now()}.webp`, { type: 'image/webp' })].slice(0, 4));
      stopCamera();
      setSheet(null);
    }, 'image/webp', 0.85);
  };

  // ——— audio note (max 60s) ———
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((m) => { try { return window.MediaRecorder.isTypeSupported(m); } catch { return false; } });
      const rec = new window.MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 64000 } : undefined);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setRecording(false);
      };
      mediaRecorderRef.current = rec;
      rec.start(250);
      setRecording(true);
      setRecSecs(0);
      recTimerRef.current = setInterval(() => {
        setRecSecs((s) => {
          if (s + 1 >= MAX_AUDIO_SECONDS) { rec.stop(); clearInterval(recTimerRef.current); return s + 1; }
          return s + 1;
        });
      }, 1000);
    } catch {
      setSheet(null); // mic denied → text stays mandatory, triage never depends on ASR
    }
  };
  const stopRecording = () => { clearInterval(recTimerRef.current); if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current?.stop(); };

  const valid = text.trim().length >= 1 && text.length <= MAX_CHARS;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!valid || submitting) return;
    // NOTE (backend media pipeline, Phase 4): today this submits one multipart
    // request the current API accepts. When pre-signed object-storage uploads
    // land, this same payload shape becomes step 1 (202 + token), with media
    // attaching asynchronously — the composer UI does not change.
    onSubmit?.({ text: text.trim(), language, district, block, geo, photos, audioBlob });
  };

  const chip = (id, Icon, label, count, disabled) => (
    <button
      key={id}
      type="button"
      disabled={disabled}
      aria-label={`${label}${count ? `, ${count} attached` : ''}`}
      onClick={() => setSheet(id)}
      className="tag-chip !py-2 hover:border-primary hover:text-primary disabled:opacity-40"
    >
      <Icon className="h-4 w-4" aria-hidden />
      {label}
      {count ? <span className="rounded-md bg-primary-subtle px-1.5 text-xs font-medium-plus text-primary">{count}</span> : null}
    </button>
  );

  return (
    <form onSubmit={handleSubmit} className="card p-5 md:p-6" aria-label="Report a civic issue">
      {/* Text — always visible, mandatory even when audio is used */}
      <label htmlFor="composer-text" className="type-label-sm">Describe the issue <span className="text-zinc-400">(required)</span></label>
      <textarea
        id="composer-text"
        rows={5}
        required
        value={text}
        onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
        placeholder="E.g. Garhwa block ke handpump mein fluoride aur peela rang aa raha hai…"
        className="input mt-2 !text-[20px] resize-none"
        aria-describedby="composer-count"
      />
      <div className="mt-1.5 flex items-center justify-between">
        <div className="flex gap-1.5" role="group" aria-label="Language preference">
          {['hindi', 'hinglish', 'english'].map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLanguage(l)}
              aria-pressed={language === l}
              className={`rounded-md px-3 py-1 text-xs font-medium-plus capitalize ${language === l ? 'bg-primary-subtle text-primary' : 'bg-surface-muted text-ink-secondary'}`}
            >
              {l === 'hinglish' ? 'Hinglish' : l[0].toUpperCase() + l.slice(1)}
            </button>
          ))}
        </div>
        <span id="composer-count" className={`font-mono text-xs ${text.length >= MAX_CHARS ? 'text-rose-600' : 'text-zinc-400'}`}>
          {text.length}/{MAX_CHARS}
        </span>
      </div>

      {/* Attachment chips — photo chip shows live compression progress */}
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Add evidence">
        {chip('photo', ImagePlus,
          compressing ? `Preparing ${compressing.done}/${compressing.total}` : 'Photo',
          !compressing && (photos.length || null))}
        {chip('camera', Camera, 'Camera', null, !canCamera || !!compressing)}
        {canRecordAudio && chip('audio', Mic, audioBlob ? 'Audio ✓' : 'Audio', audioBlob ? null : (recording ? '●' : null))}
        {chip('location', MapPin, geo ? 'Location ✓' : 'Location', null)}
      </div>
      {!canCamera && <p className="type-body-sm mt-2 text-zinc-400">This browser has no in-app camera — use Photo upload instead.</p>}
      {compressing && (
        <div
          className="mt-3"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={compressing.total}
          aria-valuenow={compressing.done}
          aria-label="Compressing photos for upload"
        >
          <div className="h-1 overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${Math.round((compressing.done / Math.max(1, compressing.total)) * 100)}%` }}
            />
          </div>
          <p className="type-body-sm mt-1.5 text-zinc-500">Compressing photo {Math.min(compressing.done + 1, compressing.total)} of {compressing.total} for upload…</p>
        </div>
      )}
      {!canRecordAudio && <p className="type-body-sm mt-2 text-zinc-400">Audio notes need a browser with recording support — your text report still works fully.</p>}

      {/* Inline previews */}
      {photos.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {photos.map((p, i) => (
            <span key={`${p.name}-${i}`} className="relative">
              <img src={URL.createObjectURL(p)} alt={`Evidence photo ${i + 1}`} className="h-16 w-16 rounded-md border border-border object-cover" />
              <button type="button" aria-label={`Remove photo ${i + 1}`} onClick={() => setPhotos((prev) => prev.filter((_, j) => j !== i))}
                className="absolute -right-1.5 -top-1.5 rounded-full bg-ink p-0.5 text-white"><X className="h-3 w-3" /></button>
            </span>
          ))}
        </div>
      )}
      {audioUrl && (
        <div className="mt-3 flex items-center gap-2 rounded-md border border-border bg-surface-muted p-2">
          <audio src={audioUrl} controls className="h-8 w-full" aria-label="Your audio note preview" />
          <button type="button" aria-label="Remove audio note" onClick={() => { setAudioBlob(null); setAudioUrl(null); }} className="p-1 text-zinc-500 hover:text-ink"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Location summary + district/block fallback (always works) */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="composer-district" className="type-label-sm">District</label>
          <select id="composer-district" value={district} onChange={(e) => setDistrict(e.target.value)} className="input mt-1.5">
            {JHARKHAND_DISTRICTS.map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="composer-block" className="type-label-sm">Block / area</label>
          <input id="composer-block" value={block} onChange={(e) => setBlock(e.target.value)} placeholder="e.g. Garhwa Sadar" className="input mt-1.5" />
        </div>
      </div>
      <p className="type-body-sm mt-2 text-zinc-500">
        {geoStatus === 'ok' && geo ? <>GPS attached: <span className="font-mono">{geo.lat}, {geo.lng}</span> — your report reaches an officer within 72 hours.</>
          : geoStatus === 'locating' ? 'Detecting your GPS location…'
          : 'GPS unavailable — your district selection is enough to route this report.'}
      </p>

      {serverError && <p role="alert" className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{serverError}</p>}

      <button type="submit" disabled={!valid || submitting || compressing} className="btn-primary mt-5 flex w-full items-center justify-center">
        {submitting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting your report…</> : compressing ? 'Preparing photos…' : 'Submit report'}
      </button>
      <p className="type-body-sm mt-2 text-center text-zinc-400">You get a tracking token immediately — photos and audio attach in the background.</p>

      {/* Inline sheets (modal) — never a page navigation */}
      {sheet === 'photo' && (
        <Sheet title="Add photos" onClose={() => setSheet(null)}>
          <input ref={fileRef} type="file" accept="image/*" multiple className="sr-only" onChange={(e) => addFiles(e.target.files)} />
          {/* Native camera sheet on mobile */}
          <input ref={cameraFileRef} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => addFiles(e.target.files)} />
          <div className="grid gap-2">
            <button type="button" onClick={() => fileRef.current?.click()} className="btn-secondary w-full">Choose from gallery</button>
            <button type="button" onClick={() => cameraFileRef.current?.click()} className="btn-secondary w-full">Take a photo now</button>
            <p className="type-body-sm text-zinc-500">Up to 4 photos. Each is resized to 1600px and compressed before upload.</p>
          </div>
        </Sheet>
      )}

      {sheet === 'camera' && (
        <Sheet title="Camera preview" onClose={() => { stopCamera(); setSheet(null); }}>
          <video ref={videoRef} playsInline muted className="aspect-video w-full rounded-md bg-ink object-cover" aria-label="Live camera preview" />
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={captureFrame} className="btn-primary flex-1">Capture</button>
            <button type="button" onClick={openCamera} className="btn-secondary">Retry</button>
          </div>
        </Sheet>
      )}

      {sheet === 'audio' && (
        <Sheet title="Audio note (optional)" onClose={() => { if (!recording) setSheet(null); }}>
          <p className="type-body-sm text-zinc-500">Max {MAX_AUDIO_SECONDS}s. Your written description stays required — triage never depends on audio alone.</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            {!recording ? (
              <button type="button" onClick={startRecording} className="btn-primary">Start recording</button>
            ) : (
              <>
                <span className="flex items-center gap-1" aria-hidden>
                  {[0, 1, 2, 3, 4].map((i) => <span key={i} className="w-1 animate-pulse rounded-full bg-primary" style={{ height: `${10 + ((recSecs + i * 7) % 18)}px` }} />)}
                </span>
                <span className="font-mono text-sm" role="timer">{recSecs}s / {MAX_AUDIO_SECONDS}s</span>
                <button type="button" onClick={stopRecording} className="btn-secondary !py-2">Stop</button>
              </>
            )}
          </div>
          {audioUrl && <audio src={audioUrl} controls className="mt-4 h-9 w-full" aria-label="Recorded audio preview" />}
        </Sheet>
      )}

      {sheet === 'location' && (
        <Sheet title="Confirm your location" onClose={() => setSheet(null)}>
          <button type="button" onClick={detectGeo} className="btn-secondary flex w-full items-center justify-center gap-2">
            <Navigation className="h-4 w-4" /> {geoStatus === 'locating' ? 'Detecting…' : 'Detect my GPS location'}
          </button>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <label className="type-label-sm">Latitude
              <input type="number" step="any" value={geo?.lat ?? ''} onChange={(e) => setGeo((g) => ({ lat: Number(e.target.value), lng: g?.lng ?? 0 }))} placeholder="23.4123" className="input mt-1" />
            </label>
            <label className="type-label-sm">Longitude
              <input type="number" step="any" value={geo?.lng ?? ''} onChange={(e) => setGeo((g) => ({ lat: g?.lat ?? 0, lng: Number(e.target.value) }))} placeholder="85.4399" className="input mt-1" />
            </label>
          </div>
          <p className="type-body-sm mt-3 text-zinc-500">Drag-to-correct map arrives with the MapLibre integration (Phase 3) — for now, edit the coordinates or rely on District + Block, which always routes correctly.</p>
        </Sheet>
      )}
    </form>
  );
}

function Sheet({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="w-full max-w-md rounded-md bg-white p-5" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-base font-medium-plus">{title}</h3>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-md border border-border p-1.5 hover:bg-surface-muted"><X className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
