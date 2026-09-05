import React from 'react';
import { Inbox } from 'lucide-react';
import { Link } from 'react-router-dom';

/**
 * EmptyState — icon + one-line copy + one action. No filler paragraphs.
 * Copy must name the specific next action (nitivayu.md §2.3).
 */
export default function EmptyState({ icon: Icon = Inbox, title, actionLabel, actionTo, onAction, className = '' }) {
  return (
    <div className={`panel-flat flex flex-col items-center px-6 py-12 text-center ${className}`}>
      <span className="flex h-11 w-11 items-center justify-center rounded-md bg-surface-muted text-ink-secondary">
        <Icon className="h-5 w-5" />
      </span>
      <p className="type-body-md mt-4 max-w-sm text-ink-secondary">{title}</p>
      {(actionLabel && (actionTo || onAction)) && (
        actionTo ? (
          <Link to={actionTo} className="btn-secondary mt-5 !py-2">{actionLabel}</Link>
        ) : (
          <button type="button" onClick={onAction} className="btn-secondary mt-5 !py-2">{actionLabel}</button>
        )
      )}
    </div>
  );
}
