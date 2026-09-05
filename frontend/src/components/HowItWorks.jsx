import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, FileText, Cpu, ShieldCheck, GraduationCap, HeartHandshake, Timer } from 'lucide-react';
import { SectionCorners } from './ui';

const STEPS = [
  { icon: FileText, title: '1. You report', copy: 'Describe the issue in Hindi, Hinglish, or English. Add photos, an audio note, and your location — or just your district. You get a tracking token in seconds.' },
  { icon: Cpu, title: '2. AI structures', copy: 'Phone numbers and Aadhaar are redacted before any model call. An extraction pass produces a title, summary, 1-of-10 category, and severity 1–5; embeddings power duplicate detection and university scoring.' },
  { icon: ShieldCheck, title: '3. Officer verifies', copy: 'A nodal officer reviews the 4-factor match (theme ×0.4, semantic ×0.3, capacity ×0.2, proximity ×0.1) and approves, overrides, or rejects within 72 hours — every decision is audit-logged.' },
  { icon: GraduationCap, title: '4. University builds', copy: 'The matched university has 7 days to accept (warning at 48h remaining, auto-reroute after). Teams form, then deliver M1 Feasibility, M2 Prototype, M3 Field Validation.' },
  { icon: HeartHandshake, title: '5. CSR funds', copy: 'Routed and accepted challenges surface to CSR desks. Pledges link to problems and teams, and disburse against verified milestones — not promises.' },
];

export default function HowItWorks() {
  // Illustration lives at frontend/public/how-it-works-city.png. Until it is
  // saved there, the hero renders single-column with no broken image.
  const [imgOk, setImgOk] = useState(true);
  return (
    <div className="bg-white">
      <section className="relative border-b border-border">
        <SectionCorners />
        <div className={`mx-auto max-w-content gap-12 px-4 py-14 md:px-6 ${imgOk ? 'grid items-center md:grid-cols-2' : ''}`}>
          <div>
            <p className="badge">How it works</p>
            <h1 className="type-display-lg mt-5 max-w-3xl text-ink">Your grievance, engineered into a solvable challenge.</h1>
            <p className="type-body-lg mt-5 max-w-2xl text-ink-secondary">Five stages, two enforceable SLAs, zero black boxes. Here is exactly what happens after you press submit.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/app/citizen/report" className="btn-primary inline-flex items-center gap-2">Report an issue <ArrowRight className="h-4 w-4" /></Link>
              <Link to="/track" className="btn-secondary">Track an existing report</Link>
            </div>
          </div>
          {imgOk && (
            <div className="relative mx-auto w-full max-w-md">
              <img
                src="/how-it-works-city.png"
                alt="A resident engaging with a smart city through the Nitivayu platform"
                className="w-full rounded-md border border-border"
                loading="eager"
                onError={() => setImgOk(false)}
              />
            </div>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-content px-4 py-12 md:px-6">
        <div className="grid gap-4 md:grid-cols-2">
          {STEPS.map(({ icon: Icon, title, copy }) => (
            <article key={title} className="card p-6">
              <span className="flex h-10 w-10 items-center justify-center rounded-md bg-surface-muted text-ink"><Icon className="h-5 w-5" /></span>
              <h2 className="mt-4 text-lg font-medium-plus text-ink">{title}</h2>
              <p className="type-body-md mt-2 text-zinc-500">{copy}</p>
            </article>
          ))}
          <article className="rounded-md bg-ink p-6 text-white">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-primary"><Timer className="h-5 w-5" /></span>
            <h2 className="mt-4 text-lg font-medium-plus" id="slas">SLAs with teeth</h2>
            <p className="type-body-md mt-2 text-white/70">Officer review: 72 hours, then escalation. University acceptance: 7 days (5 silent + 48h warning + 2-day grace), then automatic reroute. Missed deadlines are logged, never silently extended.</p>
          </article>
        </div>

        <div className="panel-flat mt-8 p-6" id="languages">
          <h2 className="text-lg font-medium-plus">Languages, devices, and low bandwidth</h2>
          <p className="type-body-md mt-2 max-w-3xl text-zinc-500">The composer works on low-end Android phones on 3G: photos compress to WebP before upload, audio caps at 60 seconds, and text plus district alone is always enough. Permissions denied? The form still submits — it never hard-blocks.</p>
        </div>

        <div className="panel-flat mt-4 p-6" id="milestones">
          <h2 className="text-lg font-medium-plus">Milestones M1–M3</h2>
          <p className="type-body-md mt-2 max-w-3xl text-zinc-500">M1 Feasibility Study &amp; Field Survey → M2 Prototype Design &amp; Lab Testing → M3 Field Validation &amp; Handover. Each step needs evidence (document, repo, or lab report) and officer verification before the next unlocks.</p>
        </div>

        <div className="panel-flat mt-4 p-6" id="funding">
          <h2 className="text-lg font-medium-plus">Funding without favoritism</h2>
          <p className="type-body-md mt-2 max-w-3xl text-zinc-500">Only routed or accepted problems accept pledges. Monthly matching maps validated challenges to corporate focus areas and exports the funding matrix for audit.</p>
        </div>
      </section>
    </div>
  );
}
