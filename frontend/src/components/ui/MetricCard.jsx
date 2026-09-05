import React from 'react';

/** MetricCard — single number, single trend, single sparkline. */
export default function MetricCard({ label, value, trend, spark = [], icon: Icon, className = '' }) {
  const points = spark.length > 1
    ? spark.map((v, i) => `${(i / (spark.length - 1)) * 100},${28 - (v / Math.max(...spark, 1)) * 24}`).join(' ')
    : '';
  return (
    <div className={`card p-5 ${className}`}>
      <div className="flex items-start justify-between">
        <p className="type-label-sm text-zinc-500">{label}</p>
        {Icon && <Icon className="h-4 w-4 text-primary" />}
      </div>
      <p className="type-display-md mt-2 !text-3xl">{value}</p>
      <div className="mt-2 flex items-end justify-between gap-3">
        {trend ? <p className="type-body-sm text-zinc-500">{trend}</p> : <span />}
        {points && (
          <svg viewBox="0 0 100 32" className="h-8 w-24 shrink-0" aria-hidden>
            <polyline points={points} fill="none" stroke="#6720FF" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
        )}
      </div>
    </div>
  );
}
