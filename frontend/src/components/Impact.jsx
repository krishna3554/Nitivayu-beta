import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { MetricCard, SectionCorners, BackgroundGrid } from './ui';
import { getDashboardStats } from '../services/api';

export default function Impact() {
  const [stats, setStats] = useState(null);
  useEffect(() => { getDashboardStats().then(({ data }) => setStats(data)).catch(() => {}); }, []);

  const cards = [
    { label: 'Reports filed', value: stats?.total_submissions ?? '—', trend: 'citizen issues ingested' },
    { label: 'Challenges triaged', value: stats?.triage_throughput ?? '—', trend: `${stats?.sla_compliance_percent ?? '—'}% routed onward` },
    { label: 'Universities active', value: stats?.active_workers ?? '—', trend: 'academic routing network', span: true },
    { label: 'CSR committed', value: stats?.total_pledged_inr != null ? `₹${Number(stats.total_pledged_inr).toLocaleString('en-IN')}` : '—', trend: 'milestone-linked funding' },
  ];

  return (
    <div className="bg-white">
      <section className="relative overflow-x-clip border-b border-border bg-grid">
        <BackgroundGrid />
        <SectionCorners />
        <div className="relative z-10 mx-auto max-w-content px-4 py-14 md:px-6">
          <p className="badge">Impact</p>
          <h1 className="type-display-lg mt-5 max-w-3xl text-ink">Progress you can audit, not just applaud.</h1>
          <p className="type-body-lg mt-5 max-w-2xl text-ink-secondary">Every number below reads from the live pipeline — submissions, routing, milestones, and pledged rupees. No vanity counters.</p>
          <div className="mt-7"><Link to="/app/citizen/report" className="btn-primary inline-flex items-center gap-2">Add your report <ArrowRight className="h-4 w-4" /></Link></div>
        </div>
      </section>
      <section className="mx-auto max-w-content px-4 py-12 md:px-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c) => <MetricCard key={c.label} {...c} />)}
        </div>
        <div className="card mt-6 p-6" id="partners">
          <h2 className="text-lg font-medium-plus">Who carries the work</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {['BIT Mesra', 'NIT Jamshedpur', 'IIT-ISM Dhanbad', 'Central University of Jharkhand', 'Ranchi University', 'XLRI Jamshedpur', 'Tata Steel CSR', 'CCL', 'BCCL', 'Vedanta'].map((p) => (
              <span key={p} className="tag-chip">{p}</span>
            ))}
          </div>
          <p className="type-body-sm mt-4 text-zinc-500" id="capacity">Capacity is load-balanced: no university is offered more than its active capacity allows, and reroutes respect current load.</p>
        </div>
      </section>
      <section className="bg-ink text-white">
        <div className="mx-auto max-w-content px-4 py-14 md:px-6">
          <h2 className="type-display-md max-w-2xl">Resolved means field-validated — not ticket-closed.</h2>
          <p className="type-body-lg mt-4 max-w-2xl text-white/70">A challenge counts as resolved only after M3 field validation is verified and the citizen’s tracker shows it. Everything else is progress, honestly labelled.</p>
        </div>
      </section>
    </div>
  );
}
