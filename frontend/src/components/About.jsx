import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export default function About() {
  return (
    <div className="bg-white">
      <section className="border-b border-border">
        <div className="mx-auto max-w-content px-4 py-14 md:px-6">
          <p className="badge">About</p>
          <h1 className="type-display-lg mt-5 max-w-3xl text-ink">Helplines close tickets. We solve problems.</h1>
          <p className="type-body-lg mt-5 max-w-2xl text-ink-secondary">
            Nitivayu (SIH26043, Governance &amp; Administration, Team QuantumQuest) connects Jharkhand’s citizens,
            nodal officers, 30+ higher-education institutions, and CSR funders into one accountable pipeline.
          </p>
          <div className="mt-7"><Link to="/how-it-works" className="btn-primary inline-flex items-center gap-2">See how it works <ArrowRight className="h-4 w-4" /></Link></div>
        </div>
      </section>
      <section className="mx-auto max-w-content grid gap-4 px-4 py-12 md:px-6 lg:grid-cols-3">
        <article className="card p-6">
          <h2 className="text-lg font-medium-plus">Control in code</h2>
          <p className="type-body-md mt-2 text-zinc-500">Durable workflows own state, retries, and SLA timers. A restart never loses your report’s place in line.</p>
        </article>
        <article className="card p-6">
          <h2 className="text-lg font-medium-plus">Judgement in AI</h2>
          <p className="type-body-md mt-2 text-zinc-500">Multilingual models structure messy reports and explain every routing score — confined to audited steps with deterministic fallbacks.</p>
        </article>
        <article className="card p-6">
          <h2 className="text-lg font-medium-plus">Accountability in humans</h2>
          <p className="type-body-md mt-2 text-zinc-500">Officers approve, universities accept, funders pledge. Every override, reroute, and verification is immutable in the audit log.</p>
        </article>
      </section>
      <section className="mx-auto max-w-content px-4 pb-14 md:px-6" id="faq">
        <div className="panel-flat p-6">
          <h2 className="text-lg font-medium-plus">Questions citizens actually ask</h2>
          <dl className="mt-4 space-y-4">
            <div><dt className="text-sm font-medium-plus">Do I need an account to report?</dt><dd className="type-body-md mt-1 text-zinc-500">Reporting uses a low-friction citizen sign-in (phone OTP). Your tracking token stays shareable without exposing your account.</dd></div>
            <div><dt className="text-sm font-medium-plus">What if I have no photo or GPS?</dt><dd className="type-body-md mt-1 text-zinc-500">Text plus district is enough. Photos, audio, and GPS strengthen your report but never gate it.</dd></div>
            <div id="contact"><dt className="text-sm font-medium-plus">Who sees my personal details?</dt><dd className="type-body-md mt-1 text-zinc-500">Phone numbers and Aadhaar are redacted before any AI call, and photo GPS metadata is stripped before storage.</dd></div>
          </dl>
        </div>
      </section>
    </div>
  );
}
