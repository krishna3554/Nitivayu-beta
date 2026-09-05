import React from 'react';

/**
 * StatusBadge — single source of truth mapping status enum → color + label.
 * Status color is scoped to this badge only (nitivayu.md §2.1); page chrome
 * stays black/white/violet per DESIGN.md.
 */
const STATUS_MAP = {
  // Intake / triage
  INGESTED: { label: 'Ingested', tone: 'muted' },
  PENDING_TRIAGE: { label: 'Awaiting triage', tone: 'pending' },
  TRIAGING: { label: 'AI triaging', tone: 'pending' },
  PENDING_OFFICER_REVIEW: { label: 'Officer review', tone: 'pending' },
  OFFICER_REVIEW: { label: 'Officer review', tone: 'pending' },
  // Routing / assignment
  PENDING_APPROVAL: { label: 'Pending approval', tone: 'pending' },
  OFFERED: { label: 'Offered', tone: 'pending' },
  ROUTED: { label: 'Routed', tone: 'violet' },
  ROUTED_TO_UNIVERSITY: { label: 'Routed', tone: 'violet' },
  // Accepted / progress
  ACCEPTED: { label: 'Accepted', tone: 'success' },
  TEAM_FORMED: { label: 'Team formed', tone: 'success' },
  SUBMITTED: { label: 'Submitted', tone: 'pending' },
  VERIFIED: { label: 'Verified', tone: 'success' },
  PLEDGED: { label: 'Pledged', tone: 'violet' },
  DISBURSED: { label: 'Disbursed', tone: 'success' },
  COMPLETED: { label: 'Resolved', tone: 'success' },
  RESOLVED: { label: 'Resolved', tone: 'success' },
  // Terminal / attention
  PENDING: { label: 'Pending', tone: 'pending' },
  DELAYED: { label: 'Delayed', tone: 'critical' },
  ESCALATED: { label: 'Escalated', tone: 'critical' },
  ESCALATED_TO_SENIOR_OFFICER: { label: 'Escalated', tone: 'critical' },
  REJECTED: { label: 'Rejected', tone: 'critical' },
  DECLINED: { label: 'Declined', tone: 'muted' },
  CANCELLED: { label: 'Cancelled', tone: 'muted' },
  EXPIRED: { label: 'Expired', tone: 'muted' },
  MERGED: { label: 'Merged', tone: 'muted' },
  DUPLICATE: { label: 'Duplicate', tone: 'muted' },
};

const TONES = {
  violet: 'bg-primary-subtle text-primary',
  pending: 'bg-amber-50 text-amber-700 border border-amber-200',
  success: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  critical: 'bg-rose-50 text-rose-700 border border-rose-200',
  muted: 'bg-surface-muted text-ink-secondary',
};

function toneDot(tone) {
  switch (tone) {
    case 'success': return 'bg-emerald-500';
    case 'pending': return 'bg-amber-500';
    case 'critical': return 'bg-rose-500';
    case 'violet': return 'bg-primary';
    default: return 'bg-zinc-400';
  }
}

export function getStatusMeta(status) {
  if (!status) return { label: 'Unknown', tone: 'muted' };
  return STATUS_MAP[String(status).toUpperCase()] || { label: String(status).replace(/_/g, ' ').toLowerCase(), tone: 'muted' };
}

export default function StatusBadge({ status, className = '' }) {
  const { label, tone } = getStatusMeta(status);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium-plus capitalize ${TONES[tone]} ${className}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${toneDot(tone)}`} aria-hidden />
      {label}
    </span>
  );
}
