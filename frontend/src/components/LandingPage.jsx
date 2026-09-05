import React, { useRef } from 'react';
import { ArrowRight, Building2, GraduationCap, Landmark, ShieldCheck, HeartHandshake, Check, ChevronLeft, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

const UNIVERSITIES = ['BIT Mesra', 'NIT Jamshedpur', 'IIT-ISM Dhanbad', 'Central University of Jharkhand', 'Ranchi University', 'XLRI Jamshedpur'];

const EXAMPLES = [
  { id: 'Garhwa fluoride', meta: 'Water · Severity 5/5', match: 'BIT Mesra · 0.912', note: '4 village handpumps grouped into one macro-challenge.' },
  { id: 'Subarnarekha effluent', meta: 'Environment · Severity 5/5', match: 'NIT Jamshedpur · 0.894', note: 'Industrial discharge routed to effluent-treatment expertise.' },
  { id: 'Jharia coal dust', meta: 'Health · Severity 4/5', match: 'IIT-ISM Dhanbad · 0.878', note: 'Hindi report triaged without translation loss.' },
  { id: 'Khunti Dokra artisans', meta: 'Livelihood · Severity 3/5', match: 'XLRI Jamshedpur · 0.865', note: 'Supply-chain challenge matched to management research.' },
];

const PIPELINE = ['Ingested', 'AI triaging', 'Officer review', 'Routed to university', 'Milestone R&D', 'Resolved'];

const PATHWAYS = [
  { icon: Landmark, title: 'Citizens', copy: 'Report in Hindi, Hinglish, or English and watch your issue move — you get a tracking token in seconds.', href: '/app/citizen/report', action: 'Report an issue' },
  { icon: ShieldCheck, title: 'Officers', copy: 'Review AI-structured challenges with an explainable 4-factor score before you approve.', href: '/login', action: 'Open officer sign-in' },
  { icon: GraduationCap, title: 'Universities', copy: 'Accept challenges matched to your departments and track M1–M3 milestones to field handover.', href: '/login', action: 'Open university sign-in' },
  { icon: HeartHandshake, title: 'CSR partners', copy: 'Pledge to routed, university-backed projects and follow every milestone to resolution.', href: '/login', action: 'Open CSR sign-in' },
];

export default function LandingPage() {
  const railRef = useRef(null);
  const scrollRail = (dir) => railRef.current?.scrollBy({ left: dir * 320, behavior: 'smooth' });
  return (
    <div className="bg-white">
      {/* Hero — two-column: copy left, pipeline visual right */}
      <section className="border-b border-border">
        <div className="mx-auto grid max-w-content items-center gap-12 px-4 py-14 md:grid-cols-2 md:px-6 md:py-20">
          <div>
            <p className="badge">Civic innovation, connected</p>
            <h1 className="type-display-lg mt-6 text-ink">From a local voice to a lasting solution.</h1>
            <p className="type-body-lg mt-6 max-w-xl text-ink-secondary">
              Nitivayu turns your grievance into a structured research challenge, routes it to the
              right university, and tracks it to a funded field solution. Helplines close tickets — you get progress you can see.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/app/citizen/report" className="btn-primary inline-flex items-center gap-2">
                Report an issue <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/track" className="btn-secondary inline-flex items-center gap-2">Track your report</Link>
            </div>
            <p className="type-body-sm mt-4 text-zinc-500">Your report reaches an officer within 72 hours. Your tracking token stays public — your account stays private.</p>
          </div>

          {/* Data visualization (right) — centered against the hero text block */}
          <div className="relative mx-auto w-full max-w-md">
            <span aria-hidden className="absolute -left-3 -top-3 h-6 w-6 border-l-2 border-t-2 border-primary" />
            <span aria-hidden className="absolute -right-3 -top-3 h-6 w-6 border-r-2 border-t-2 border-primary" />
            <span aria-hidden className="absolute -bottom-3 -left-3 h-6 w-6 border-b-2 border-l-2 border-primary" />
            <span aria-hidden className="absolute -bottom-3 -right-3 h-6 w-6 border-b-2 border-r-2 border-primary" />
            <div className="card p-6">
              <p className="type-caption text-primary">Live pipeline</p>
              <ol className="mt-4 space-y-3">
                {PIPELINE.map((step, i) => (
                  <li key={step} className="flex items-center gap-3">
                    <span className={`flex h-6 w-6 items-center justify-center rounded-md text-xs font-medium-plus ${i < 3 ? 'bg-emerald-500 text-white' : i === 3 ? 'bg-primary-subtle text-primary' : 'bg-surface-muted text-zinc-400'}`}>
                      {i < 3 ? <Check className="h-3.5 w-3.5" /> : i + 1}
                    </span>
                    <span className={`text-sm ${i === 3 ? 'font-medium-plus text-ink' : 'text-ink-secondary'}`}>{step}</span>
                    {i === 3 && <span className="tag-chip ml-auto !text-xs">BIT Mesra · 0.912</span>}
                  </li>
                ))}
              </ol>
              <div className="mt-5 grid grid-cols-3 gap-px overflow-hidden rounded-md border border-border bg-border">
                {[['72h', 'officer SLA'], ['7d', 'university SLA'], ['M1–M3', 'milestones']].map(([v, l]) => (
                  <div key={l} className="bg-white px-3 py-3 text-center">
                    <p className="text-lg font-medium-plus text-ink">{v}</p>
                    <p className="text-xs text-zinc-500">{l}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Horizontally scrollable university strip */}
        <div className="border-t border-border">
          <div className="scrollbar-thin mx-auto flex max-w-content gap-2 overflow-x-auto px-4 py-4 md:px-6" aria-label="University network">
            {UNIVERSITIES.map((u) => <span key={u} className="tag-chip shrink-0">{u}</span>)}
          </div>
        </div>
      </section>

      {/* Example challenges carousel — arrows + snap, no native scrollbar */}
      <section className="mx-auto max-w-content px-4 py-14 md:px-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="type-caption text-primary">Grounded in real Jharkhand challenges</p>
            <h2 className="type-display-md mt-3 max-w-2xl text-ink">Messy reports in. Research-ready challenges out.</h2>
          </div>
          <div className="hidden shrink-0 gap-2 sm:flex" role="group" aria-label="Scroll case studies">
            <button type="button" onClick={() => scrollRail(-1)} aria-label="Previous case studies" className="rounded-md border border-border p-2 text-ink-secondary hover:border-primary hover:text-primary">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => scrollRail(1)} aria-label="Next case studies" className="rounded-md border border-border p-2 text-ink-secondary hover:border-primary hover:text-primary">
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div ref={railRef} className="-mx-4 mt-8 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 [scrollbar-width:none] md:mx-0 md:px-0 [&::-webkit-scrollbar]:hidden">
          {EXAMPLES.map((c) => (
            <article key={c.id} className="card w-72 shrink-0 snap-start p-5">
              <p className="type-caption text-zinc-400">{c.meta}</p>
              <h3 className="mt-2 text-base font-medium-plus text-ink">{c.id}</h3>
              <p className="type-body-sm mt-2 text-zinc-500">{c.note}</p>
              <p className="mt-4 font-mono text-xs text-primary">{c.match}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Black testimonial band — three-column quote grid */}
      <section className="bg-ink text-white">
        <div className="mx-auto max-w-content px-4 py-14 md:px-6 md:py-20">
          <p className="type-caption text-white/50">Accountability at every step</p>
          <h2 className="type-display-md mt-3 max-w-2xl">AI proposes. Humans decide. Records prove it.</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {[
              ['“I approve a match when I can see why — the 4-factor breakdown shows its work.”', 'Nodal Officer', 'District verification gate · 72h SLA'],
              ['“Our students finally get field problems worth a thesis — with funding attached.”', 'IIC Coordinator', 'University workspace · 7-day acceptance SLA'],
              ['“We pledge where milestones are public. No black box, no vanity metrics.”', 'CSR Desk', 'Corporate workspace · milestone-linked funding'],
            ].map(([quote, name, role]) => (
              <figure key={name} className="rounded-md border border-white/15 p-6">
                <blockquote className="type-body-lg-medium text-white">{quote}</blockquote>
                <figcaption className="mt-5">
                  <p className="text-sm font-medium-plus">{name}</p>
                  <p className="type-body-sm text-white/60">{role}</p>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      {/* Role entry points */}
      <section className="mx-auto max-w-content px-4 py-14 md:px-6 md:py-20">
        <p className="type-caption text-primary">One connected civic system</p>
        <div className="mt-3 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <h2 className="type-display-md text-ink">Find your place in the flow.</h2>
          <p className="type-body-md max-w-md text-zinc-500">Each workspace loads only what your role can use — nothing disabled, nothing leaked.</p>
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PATHWAYS.map(({ icon: Icon, title, copy, href, action }) => (
            <div key={title} className="card p-5">
              <span className="flex h-10 w-10 items-center justify-center rounded-md bg-surface-muted text-ink"><Icon className="h-5 w-5" /></span>
              <h3 className="mt-5 text-lg font-medium-plus text-ink">{title}</h3>
              <p className="type-body-sm mt-2 min-h-16 text-zinc-500">{copy}</p>
              <Link to={href} className="link-inline mt-4 inline-flex items-center gap-1 !text-sm font-medium-plus">{action} <ArrowRight className="h-4 w-4" /></Link>
            </div>
          ))}
        </div>
      </section>

      {/* Closing band (black) — single secondary action on dark */}
      <section className="bg-ink px-4 py-14 text-white md:px-6">
        <div className="mx-auto flex max-w-content flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex gap-4">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-primary"><Building2 className="h-5 w-5" /></span>
            <div>
              <h2 className="text-2xl font-medium-plus tracking-tight">Better civic outcomes start with one report.</h2>
              <p className="type-body-sm mt-1 text-white/60">Make your community’s challenge visible to the people equipped to solve it.</p>
            </div>
          </div>
          <Link to="/app/citizen/report" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-white px-5 py-3 text-sm font-medium-plus text-ink">Start a report <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </section>
    </div>
  );
}
