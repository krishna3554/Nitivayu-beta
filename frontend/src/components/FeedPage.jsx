import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  BadgeCheck,
  LocateFixed,
  MapPin,
  MessageCircle,
  Music,
  Share2,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react';
import {
  BackgroundGrid,
  EmptyState,
  SeverityBadge,
  StatusBadge,
} from './ui';
import { useAuth } from '../lib/auth';
import { useMetaConfig } from '../lib/meta';
import {
  confirmReport,
  feedMediaUrl,
  getFeed,
  getFeedComments,
  getFeedMediaList,
  meTooReport,
  postFeedComment,
} from '../services/api';

const PAGE_SIZE = 12;

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'ingested', label: 'Ingested' },
  { value: 'routed', label: 'Routed' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
];

function timeAgo(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const mins = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

/**
 * Public Reports Feed — every triaged citizen report, visible to the community.
 * Read is free (no login); me-too / confirm / comment need a citizen account
 * (phone-OTP), redirecting back here after sign-in. Built as its own page and
 * data flow — not the officer queue: no GPS, no AI scores, no officer fields.
 */
export default function FeedPage() {
  const { config } = useMetaConfig();
  const [filters, setFilters] = useState({ district: '', category: '', status: '' });
  const [near, setNear] = useState(null); // {lat, lng} | null
  const [geoState, setGeoState] = useState('idle'); // idle|locating|ok|denied|unsupported
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const sentinelRef = useRef(null);

  const load = useCallback(async (reset, nearOverride) => {
    const activeNear = nearOverride !== undefined ? nearOverride : near;
    const skip = reset ? 0 : items.length;
    if (reset) setLoading(true);
    else setLoadingMore(true);
    setError('');
    try {
      const params = {
        skip,
        limit: PAGE_SIZE,
        ...(filters.district ? { district: filters.district } : {}),
        ...(filters.category ? { category: filters.category } : {}),
        ...(filters.status ? { status: filters.status } : {}),
        ...(activeNear ? { near_lat: activeNear.lat, near_lng: activeNear.lng } : {}),
      };
      const { data } = await getFeed(params);
      setItems((prev) => (reset ? data.items : [...prev, ...data.items]));
      setTotal(data.total);
    } catch {
      setError('We could not load community reports. Check your connection and try again.');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, near, items.length]);

  // Reset the list whenever filters or location change.
  useEffect(() => {
    setItems([]);
    load(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, near]);

  // Infinite scroll with a sentinel; the Load-more button below is the fallback.
  const hasMore = items.length < total;
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || loading || loadingMore || !hasMore) return;
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) load(false); },
      { rootMargin: '600px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [load, loading, loadingMore, hasMore]);

  // Same geolocation permission pattern as the report composer: browser-owned
  // prompt, district dropdowns keep working when permission is denied.
  const toggleNearMe = () => {
    if (near) { setNear(null); setGeoState('idle'); return; }
    if (!('geolocation' in navigator)) { setGeoState('unsupported'); return; }
    setGeoState('locating');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setNear({ lat: Number(pos.coords.latitude.toFixed(6)), lng: Number(pos.coords.longitude.toFixed(6)) });
        setGeoState('ok');
      },
      () => setGeoState('denied'),
      { timeout: 8000, maximumAge: 60000 },
    );
  };

  const updateItem = (problemId, patch) =>
    setItems((prev) => prev.map((it) => (it.problem_id === problemId ? { ...it, ...patch } : it)));

  return (
    <div className="relative mx-auto min-h-[calc(100vh-73px)] max-w-content overflow-x-clip bg-grid px-4 py-10 md:px-6">
      <BackgroundGrid />
      <div className="relative z-10 mx-auto max-w-2xl">
        <p className="type-caption text-primary">Community reports</p>
        <h1 className="type-display-md mt-3 text-ink">Reports feed</h1>
        <p className="type-body-md mt-3 text-zinc-500">
          Every triaged citizen report, visible to everyone. No sign-in needed to browse —
          sign in only to say “me too”, confirm, or comment.
        </p>

        {/* Filters — district / category / status + Near-me toggle */}
        <div className="card mt-6 p-4 md:p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="type-label-sm text-zinc-500">District</span>
              <select
                value={filters.district}
                onChange={(e) => setFilters((f) => ({ ...f, district: e.target.value }))}
                className="input mt-1.5"
                aria-label="Filter by district"
              >
                <option value="">All districts</option>
                {(config.districts || []).map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="type-label-sm text-zinc-500">Category</span>
              <select
                value={filters.category}
                onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
                className="input mt-1.5"
                aria-label="Filter by category"
              >
                <option value="">All categories</option>
                {(config.categories || []).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="type-label-sm text-zinc-500">Status</span>
              <select
                value={filters.status}
                onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
                className="input mt-1.5"
                aria-label="Filter by status"
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={toggleNearMe}
              aria-pressed={Boolean(near)}
              className={near ? 'btn-primary !py-2' : 'btn-secondary !py-2'}
            >
              <span className="inline-flex items-center gap-2">
                <LocateFixed className="h-4 w-4" />
                {near ? 'Near you first · on' : 'Near me'}
              </span>
            </button>
            {geoState === 'locating' && <span className="text-sm text-zinc-500">Locating…</span>}
            {geoState === 'denied' && <span className="text-sm text-zinc-500">Location blocked — district filter still works.</span>}
            {geoState === 'unsupported' && <span className="text-sm text-zinc-500">Geolocation not supported here.</span>}
            {!loading && (
              <span className="ml-auto text-sm text-zinc-500" role="status">
                {total === 0 ? 'No reports' : `${total} report${total === 1 ? '' : 's'}`}
              </span>
            )}
          </div>
        </div>

        {/* List */}
        {loading && (
          <div className="mt-6 space-y-4" aria-label="Loading reports">
            {[0, 1, 2].map((i) => (
              <div key={i} className="card animate-pulse p-6">
                <div className="h-4 w-2/3 rounded-sm bg-surface-muted" />
                <div className="mt-3 h-3 w-full rounded-sm bg-surface-muted" />
                <div className="mt-2 h-3 w-5/6 rounded-sm bg-surface-muted" />
              </div>
            ))}
          </div>
        )}

        {error && !loading && (
          <div className="card mt-6 border-rose-200 bg-rose-50 p-6 text-center">
            <p className="text-sm text-rose-700">{error}</p>
            <button type="button" onClick={() => load(true)} className="btn-secondary mt-4 !py-2">Retry</button>
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <EmptyState
            title={filters.district || filters.category || filters.status
              ? 'No reports match these filters yet.'
              : 'No reports in this district yet.'}
            actionLabel="Report an issue"
            actionTo="/app/citizen/report"
            className="mt-6"
          />
        )}

        {!loading && !error && items.length > 0 && (
          <ol className="mt-6 space-y-4">
            {items.map((item) => (
              <ReportCard key={item.problem_id} item={item} onUpdate={updateItem} />
            ))}
          </ol>
        )}

        <div ref={sentinelRef} aria-hidden className="h-1" />
        {loadingMore && <p className="mt-4 text-center text-sm text-zinc-500">Loading more reports…</p>}
        {!loading && !loadingMore && hasMore && (
          <div className="mt-4 text-center">
            <button type="button" onClick={() => load(false)} className="btn-secondary !py-2">Load more</button>
          </div>
        )}
      </div>
    </div>
  );
}

function ReportCard({ item, onUpdate }) {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [media, setMedia] = useState(null); // {assets} once expanded
  const [lightbox, setLightbox] = useState(null); // asset index
  const [busy, setBusy] = useState(null); // me-too | confirm | null
  const [notice, setNotice] = useState('');
  const [copied, setCopied] = useState(false);

  const needAuth = () => {
    if (!session) {
      navigate(`/login?next=${encodeURIComponent('/feed')}`);
      return true;
    }
    return false;
  };

  const ensureMedia = async () => {
    if (media || (!item.photo_count && !item.has_audio)) return;
    try {
      const { data } = await getFeedMediaList(item.problem_id);
      setMedia(data);
    } catch { /* cover image alone still tells the story */ }
  };

  const toggleExpandMedia = () => {
    if (item.photo_count > 1 || item.has_audio) ensureMedia();
    setExpanded((v) => !v);
  };

  const handleMeToo = async () => {
    if (needAuth() || busy) return;
    if (item.me_too_by_me) { setNotice('You already marked “me too” on this report.'); return; }
    setBusy('me-too');
    setNotice('');
    try {
      const { data } = await meTooReport(item.problem_id);
      onUpdate(item.problem_id, { me_too_by_me: true, me_too_count: data.me_too_count });
    } catch (err) {
      const status = err.response?.status;
      if (status === 409) {
        onUpdate(item.problem_id, { me_too_by_me: true });
        setNotice('You already marked “me too” on this report.');
      } else if (status === 401 || status === 403) {
        navigate(`/login?next=${encodeURIComponent('/feed')}`);
      } else {
        setNotice(err.response?.data?.detail || 'Could not record “me too”. Try again.');
      }
    } finally {
      setBusy(null);
    }
  };

  const handleConfirm = async () => {
    if (needAuth() || busy) return;
    if (item.confirmed_by_me) { setNotice('You already confirmed this report.'); return; }
    setBusy('confirm');
    setNotice('');
    try {
      const { data } = await confirmReport(item.problem_id);
      onUpdate(item.problem_id, { confirmed_by_me: true, confirm_count: data.confirm_count });
    } catch (err) {
      const status = err.response?.status;
      if (status === 409) {
        onUpdate(item.problem_id, { confirmed_by_me: true });
        setNotice('You already confirmed this report.');
      } else if (status === 401 || status === 403) {
        navigate(`/login?next=${encodeURIComponent('/feed')}`);
      } else {
        setNotice(err.response?.data?.detail || 'Could not record confirmation. Try again.');
      }
    } finally {
      setBusy(null);
    }
  };

  const handleShare = async () => {
    const url = `${window.location.origin}/track/${item.tracking_token}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setNotice('Copy this link: ' + url);
    }
  };

  const photos = (media?.assets || []).filter((a) => a.kind === 'photo');
  const audio = (media?.assets || []).find((a) => a.kind === 'audio');
  const extraPhotos = Math.max(0, (item.photo_count || 0) - 1);
  const location = [item.block, item.district].filter(Boolean).join(', ') || 'Jharkhand';

  return (
    <li className="card overflow-hidden">
      <div className="p-5 md:p-6">
        {/* Header: anonymized byline · relative time · muted token */}
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <p className="text-sm font-medium-plus text-ink">
            Citizen report <span className="font-normal text-zinc-500">· {item.district || 'Jharkhand'}</span>
          </p>
          <p className="flex items-center gap-2 text-xs text-zinc-400">
            <time dateTime={item.created_at || undefined}>{timeAgo(item.created_at)}</time>
            {item.tracking_token && <span className="font-mono">{item.tracking_token}</span>}
          </p>
        </div>

        {/* Badge row: same vocabulary as every workspace */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {item.category && <span className="tag-chip !text-xs">{item.category}</span>}
          {item.severity != null && <SeverityBadge value={item.severity} />}
          <StatusBadge status={item.status} />
          {item.matched_university && (
            <span className="text-xs text-zinc-500">→ {item.matched_university}</span>
          )}
        </div>

        <h2 className="mt-3 text-lg font-medium-plus text-ink">{item.title}</h2>
        {item.summary && (
          <div className="mt-1.5">
            <p className={`type-body-sm text-zinc-500 ${expanded ? '' : 'line-clamp-3'}`}>{item.summary}</p>
            {item.summary.length > 180 && (
              <button type="button" onClick={() => setExpanded((v) => !v)} className="link-inline !text-sm font-medium-plus">
                {expanded ? 'Show less' : 'Read more'}
              </button>
            )}
          </div>
        )}

        {/* Media: first clean photo as cover (lazy); extras + audio expand inline */}
        {item.cover_asset_id && (
          <figure className="mt-4">
            <button
              type="button"
              onClick={toggleExpandMedia}
              className="relative block w-full overflow-hidden rounded-md border border-border"
              aria-label={extraPhotos > 0 ? `Open all ${item.photo_count} photos` : 'Open photo'}
            >
              <img
                src={feedMediaUrl(item.cover_asset_id)}
                alt={`Community report photo — ${item.title}`}
                loading="lazy"
                className="max-h-72 w-full object-cover"
              />
              {extraPhotos > 0 && (
                <span className="absolute bottom-2 right-2 rounded-sm bg-black/70 px-2 py-1 text-xs font-medium-plus text-white">
                  +{extraPhotos} photo{extraPhotos === 1 ? '' : 's'}
                </span>
              )}
            </button>
            {expanded && photos.length > 1 && (
              <div className="mt-2 grid grid-cols-3 gap-2">
                {photos.slice(1).map((p, i) => (
                  <button
                    key={p.asset_id}
                    type="button"
                    onClick={() => setLightbox(i + 1)}
                    className="overflow-hidden rounded-sm border border-border"
                    aria-label={`Open photo ${i + 2}`}
                  >
                    <img src={feedMediaUrl(p.asset_id)} alt="" loading="lazy" className="h-20 w-full object-cover" />
                  </button>
                ))}
              </div>
            )}
            {expanded && item.has_audio && (
              <div className="mt-2 flex items-center gap-2 rounded-sm border border-border bg-surface-muted px-3 py-2">
                <Music className="h-4 w-4 shrink-0 text-zinc-400" aria-hidden />
                {audio ? (
                  <audio controls preload="none" src={feedMediaUrl(audio.asset_id)} className="h-8 w-full" aria-label="Community audio note" />
                ) : (
                  <button type="button" onClick={ensureMedia} className="link-inline !text-sm font-medium-plus">Load audio note</button>
                )}
              </div>
            )}
            {!expanded && item.has_audio && (
              <button type="button" onClick={toggleExpandMedia} className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium-plus text-zinc-500 hover:text-ink">
                <Music className="h-3.5 w-3.5" aria-hidden /> Audio note attached
              </button>
            )}
          </figure>
        )}
        {!item.cover_asset_id && item.has_audio && (
          <button type="button" onClick={toggleExpandMedia} className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium-plus text-zinc-500 hover:text-ink">
            <Music className="h-3.5 w-3.5" aria-hidden /> Audio note attached
          </button>
        )}
        {expanded && !item.cover_asset_id && item.has_audio && !audio && (
          <div className="mt-2 rounded-sm border border-border bg-surface-muted px-3 py-2">
            <button type="button" onClick={ensureMedia} className="link-inline !text-sm font-medium-plus">Load audio note</button>
          </div>
        )}

        {/* Location: block/district text only — never exact GPS */}
        <p className="mt-3 flex items-center gap-1.5 text-sm text-zinc-500">
          <MapPin className="h-4 w-4 shrink-0 text-zinc-400" aria-hidden /> {location}
        </p>

        {/* Engagement: civic actions only — no emoji reactions */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <button
            type="button"
            onClick={handleMeToo}
            disabled={busy === 'me-too'}
            aria-pressed={Boolean(item.me_too_by_me)}
            title="I experience this issue too — raises its priority"
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium-plus transition-colors ${
              item.me_too_by_me
                ? 'bg-primary-subtle text-primary'
                : 'bg-surface-muted text-ink-secondary hover:text-primary'
            }`}
          >
            <Users className="h-4 w-4" aria-hidden />
            Me too{item.me_too_count > 0 && <span aria-label={`${item.me_too_count} me-toos`}> · {item.me_too_count}</span>}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={busy === 'confirm'}
            aria-pressed={Boolean(item.confirmed_by_me)}
            title="I have seen this issue firsthand nearby"
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium-plus transition-colors ${
              item.confirmed_by_me
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-surface-muted text-ink-secondary hover:text-emerald-700'
            }`}
          >
            <BadgeCheck className="h-4 w-4" aria-hidden />
            Confirm{item.confirm_count > 0 && <span aria-label={`${item.confirm_count} confirmations`}> · {item.confirm_count}</span>}
          </button>
          <button
            type="button"
            onClick={() => setShowComments((v) => !v)}
            aria-expanded={showComments}
            className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1.5 text-xs font-medium-plus text-ink-secondary hover:text-primary"
          >
            <MessageCircle className="h-4 w-4" aria-hidden />
            Comment{item.comment_count > 0 && <span aria-label={`${item.comment_count} comments`}> · {item.comment_count}</span>}
          </button>
          <button
            type="button"
            onClick={handleShare}
            className="inline-flex items-center gap-1.5 rounded-md bg-surface-muted px-2.5 py-1.5 text-xs font-medium-plus text-ink-secondary hover:text-primary"
          >
            <Share2 className="h-4 w-4" aria-hidden />
            {copied ? 'Link copied' : 'Share'}
          </button>
          {!session && (
            <Link to={`/login?next=${encodeURIComponent('/feed')}`} className="ml-auto text-xs font-medium-plus text-zinc-400 hover:text-primary">
              Sign in to react
            </Link>
          )}
        </div>
        {notice && <p className="mt-2 text-xs text-zinc-500" role="status">{notice}</p>}

        {showComments && (
          <CommentsThread
            problemId={item.problem_id}
            onCount={(n) => onUpdate(item.problem_id, { comment_count: n })}
          />
        )}
      </div>

      {/* Trust strip: what separates this feed from a generic complaints board */}
      {item.officer_verified && (
        <div className="flex items-center gap-2 border-t border-emerald-200 bg-emerald-50/50 px-5 py-2.5 md:px-6">
          <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-700" aria-hidden />
          <p className="text-xs font-medium-plus text-emerald-800">
            Officer-verified{item.matched_university ? ` · matched to ${item.matched_university}` : ''}
          </p>
        </div>
      )}

      {/* Lightbox for extra photos */}
      {lightbox !== null && photos.length > 0 && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Photo viewer"
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4"
          onClick={() => setLightbox(null)}
        >
          <button
            type="button"
            onClick={() => setLightbox(null)}
            aria-label="Close photo viewer"
            className="absolute right-4 top-4 rounded-md bg-white/10 p-2 text-white hover:bg-white/20"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={feedMediaUrl(photos[lightbox % photos.length].asset_id)}
            alt=""
            className="max-h-[85vh] max-w-full rounded-md object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {photos.length > 1 && (
            <div className="absolute bottom-4 flex items-center gap-3">
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setLightbox((lightbox - 1 + photos.length) % photos.length); }}
                className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium-plus text-white hover:bg-white/20"
              >
                ← Prev
              </button>
              <span className="text-xs text-white/80">{(lightbox % photos.length) + 1} / {photos.length}</span>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setLightbox((lightbox + 1) % photos.length); }}
                className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium-plus text-white hover:bg-white/20"
              >
                Next →
              </button>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function CommentsThread({ problemId, onCount }) {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [comments, setComments] = useState(null);
  const [draft, setDraft] = useState('');
  const [replyTo, setReplyTo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    getFeedComments(problemId)
      .then(({ data }) => { if (live) { setComments(data.comments || []); onCount((data.comments || []).length); } })
      .catch(() => { if (live) setError('Could not load comments.'); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [problemId]);

  const submit = async (e) => {
    e.preventDefault();
    if (!session) { navigate(`/login?next=${encodeURIComponent('/feed')}`); return; }
    if (!draft.trim() || busy) return;
    setBusy(true);
    setError('');
    try {
      const { data } = await postFeedComment(problemId, { body: draft.trim(), parent_id: replyTo });
      setComments((prev) => [...(prev || []), data]);
      onCount((comments || []).length + 1);
      setDraft('');
      setReplyTo(null);
    } catch (err) {
      const status = err.response?.status;
      if (status === 401 || status === 403) navigate(`/login?next=${encodeURIComponent('/feed')}`);
      else setError(err.response?.data?.detail || 'Could not post your comment. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const topLevel = (comments || []).filter((c) => !c.parent_id);
  const repliesOf = (id) => (comments || []).filter((c) => c.parent_id === id);
  const replyTarget = replyTo ? (comments || []).find((c) => c.comment_id === replyTo) : null;

  return (
    <div className="mt-4 rounded-md border border-border bg-surface-muted p-4">
      <h3 className="type-label-sm text-zinc-500">Discussion</h3>
      {comments === null && !error && <p className="mt-2 text-sm text-zinc-500">Loading comments…</p>}
      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}
      {comments !== null && comments.length === 0 && (
        <p className="mt-2 text-sm text-zinc-500">No comments yet — be the first to add context.</p>
      )}
      {topLevel.length > 0 && (
        <ul className="mt-3 space-y-3">
          {topLevel.map((c) => (
            <li key={c.comment_id}>
              <div className="rounded-sm border border-border bg-white px-3 py-2">
                <p className="flex items-baseline justify-between gap-2">
                  <span className="text-xs font-medium-plus text-ink">{c.author}</span>
                  <time className="text-[11px] text-zinc-400">{timeAgo(c.created_at)}</time>
                </p>
                <p className="mt-1 text-sm text-ink-secondary">{c.body}</p>
                <button
                  type="button"
                  onClick={() => setReplyTo(c.comment_id)}
                  className="mt-1 text-xs font-medium-plus text-zinc-400 hover:text-primary"
                >
                  Reply
                </button>
              </div>
              {repliesOf(c.comment_id).map((r) => (
                <div key={r.comment_id} className="ml-5 mt-2 rounded-sm border border-border bg-white px-3 py-2">
                  <p className="flex items-baseline justify-between gap-2">
                    <span className="text-xs font-medium-plus text-ink">{r.author}</span>
                    <time className="text-[11px] text-zinc-400">{timeAgo(r.created_at)}</time>
                  </p>
                  <p className="mt-1 text-sm text-ink-secondary">{r.body}</p>
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="mt-3">
        {replyTarget && (
          <p className="mb-2 flex items-center justify-between text-xs text-zinc-500">
            <span>Replying to {replyTarget.author}</span>
            <button type="button" onClick={() => setReplyTo(null)} className="font-medium-plus hover:text-ink">Cancel</button>
          </p>
        )}
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={1000}
          rows={2}
          placeholder={session ? 'Add helpful context…' : 'Sign in to join the discussion…'}
          aria-label="Write a comment"
          className="input !text-sm"
        />
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[11px] text-zinc-400">{draft.length}/1000 · moderated for spam and abuse</span>
          <button type="submit" disabled={busy || !draft.trim()} className="btn-primary !px-4 !py-1.5 !text-sm disabled:opacity-60">
            {session ? 'Post' : 'Sign in to post'}
          </button>
        </div>
      </form>
    </div>
  );
}
