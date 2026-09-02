import React from 'react';
import { ArrowRight, Building2, GraduationCap, HeartHandshake, Landmark, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

const pathways = [
  { icon: Landmark, title: 'Citizens', copy: 'Turn a local concern into a visible, trackable civic challenge.', href: '/report', action: 'Report an issue', iconClass: 'bg-emerald-50 text-emerald-600' },
  { icon: ShieldCheck, title: 'Officers', copy: 'Review AI-assisted triage and route verified challenges with confidence.', href: '/officer', action: 'Open review queue', iconClass: 'bg-indigo-50 text-indigo-600' },
  { icon: GraduationCap, title: 'Universities', copy: 'Work on high-impact challenges matched to your department’s expertise.', href: '/university', action: 'View workspace', iconClass: 'bg-sky-50 text-sky-600' },
  { icon: HeartHandshake, title: 'CSR partners', copy: 'Fund transparent, milestone-led solutions for communities that need them.', href: '/csr', action: 'Explore projects', iconClass: 'bg-amber-50 text-amber-600' },
];

export default function LandingPage() {
  return (
    <div className="overflow-hidden bg-slate-50">
      <section className="relative isolate border-b border-slate-200 bg-white">
        <div className="absolute inset-0 -z-10 opacity-60 [background-image:linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] [background-size:42px_42px]"></div>
        <div className="absolute -top-40 right-[-8rem] -z-10 h-96 w-96 rounded-full bg-emerald-100 blur-3xl"></div>
        <div className="max-w-7xl mx-auto px-6 py-20 md:py-28">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.18em] text-emerald-800">
              <Sparkles className="w-3.5 h-3.5" /> Civic innovation, connected
            </div>
            <h1 className="mt-7 text-5xl font-black tracking-[-0.055em] text-zinc-950 sm:text-6xl md:text-7xl leading-[0.94]">
              From a local voice to a lasting solution.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-zinc-600">
              Nitivayu connects citizen-reported issues with accountable officers, university problem-solvers, and CSR funding—so urgent problems become measurable public progress.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link to="/report" className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-zinc-900/15 transition hover:-translate-y-0.5 hover:bg-zinc-800">
                Report an issue <ArrowRight className="w-4 h-4" />
              </Link>
              <Link to="/report" className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-bold text-zinc-800 transition hover:border-zinc-500 hover:bg-slate-50">
                Start with your issue
              </Link>
            </div>
          </div>
          <div className="mt-16 grid max-w-4xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200 shadow-sm md:grid-cols-4">
            {[["4", "connected groups"], ["3", "languages supported"], ["24/7", "issue intake"], ["1", "shared mission"]].map(([value, label]) => (
              <div key={label} className="bg-white px-5 py-5">
                <p className="text-2xl font-black tracking-tight text-zinc-900">{value}</p>
                <p className="mt-1 text-xs font-medium text-zinc-500">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 py-20">
        <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-600">One connected civic system</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-zinc-900">Find your place in the flow.</h2>
          </div>
          <p className="max-w-md text-sm leading-6 text-zinc-600">Each portal preserves a clear responsibility while keeping the full journey transparent.</p>
        </div>
        <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {pathways.map(({ icon: Icon, title, copy, href, action, iconClass }) => (
            <Link key={title} to={href} className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-lg">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconClass}`}><Icon className="w-5 h-5" /></div>
              <h3 className="mt-6 text-lg font-bold text-zinc-900">{title}</h3>
              <p className="mt-2 min-h-16 text-sm leading-6 text-zinc-600">{copy}</p>
              <span className="mt-5 inline-flex items-center gap-1 text-sm font-bold text-zinc-900 group-hover:text-indigo-700">{action} <ArrowRight className="w-4 h-4" /></span>
            </Link>
          ))}
        </div>
      </section>

      <section className="bg-zinc-900 px-6 py-16 text-white">
        <div className="max-w-7xl mx-auto flex flex-col gap-7 md:flex-row md:items-center md:justify-between">
          <div className="flex gap-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-emerald-500"><Building2 className="w-5 h-5" /></div><div><h2 className="text-2xl font-bold">Better civic outcomes start with one report.</h2><p className="mt-1 text-sm text-zinc-400">Make your community’s challenge visible to the people equipped to solve it.</p></div></div>
          <Link to="/report" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-bold text-zinc-900 transition hover:bg-emerald-50">Start a report <ArrowRight className="w-4 h-4" /></Link>
        </div>
      </section>
    </div>
  );
}
