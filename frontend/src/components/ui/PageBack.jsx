import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

/** Breadcrumb back-link for workspace deep pages (never sidebar-only navigation). */
export default function PageBack({ to, label, className = '' }) {
  return (
    <Link to={to} className={`link-inline inline-flex items-center gap-1.5 !text-sm font-medium-plus ${className}`}>
      <ArrowLeft className="h-4 w-4" aria-hidden />
      {label}
    </Link>
  );
}
