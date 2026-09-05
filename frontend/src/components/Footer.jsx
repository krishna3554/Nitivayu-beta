import React from 'react';
import { Link } from 'react-router-dom';

const COLS = [
  {
    title: 'Citizens',
    links: [
      ['Report an issue', '/app/citizen/report'], ['Track your report', '/track'], ['How it works', '/how-it-works'],
      ['Impact stories', '/impact'], ['About Nitivayu', '/about'], ['Language support', '/how-it-works#languages'],
      ['Help & FAQ', '/about#faq'], ['Contact', '/about#contact'],
    ],
  },
  {
    title: 'Officers',
    links: [
      ['Officer console', '/app/officer'], ['Review queue', '/app/officer'], ['Batch control', '/app/officer/batch'],
      ['Escalations', '/app/officer/escalations'], ['Compliance exports', '/app/admin/exports'], ['SLA policy', '/how-it-works#slas'],
      ['Sign in', '/login'], ['Invite requests', '/signup'],
    ],
  },
  {
    title: 'Academia',
    links: [
      ['University workspace', '/app/university'], ['Challenge inbox', '/app/university'], ['Active projects', '/app/university/projects'],
      ['Milestones M1–M3', '/how-it-works#milestones'], ['IIC onboarding', '/signup'], ['Capacity norms', '/impact#capacity'],
      ['Sign in', '/login'], ['Partner list', '/impact#partners'],
    ],
  },
  {
    title: 'Funding & Admin',
    links: [
      ['CSR workspace', '/app/corporate'], ['Opportunities', '/app/corporate'], ['Pledge flow', '/how-it-works#funding'],
      ['Portfolio', '/app/corporate/portfolio'], ['Admin control plane', '/app/admin'], ['Telemetry', '/app/admin/telemetry'],
      ['Audit trail', '/app/admin/exports'], ['Sign in', '/login'],
    ],
  },
];

/** Fireworks footer: static full-bleed black band, reduced-opacity white links. */
export default function Footer() {
  return (
    <footer className="static bg-ink text-white">
      <div className="mx-auto max-w-content px-4 py-14 md:min-h-[624px] md:px-6 md:py-16">
        <div className="flex flex-col justify-between gap-10 md:flex-row">
          <div className="max-w-sm">
            <p className="flex items-center gap-2">
              <img
                src="/nitivayu-mark.png"
                srcSet="/nitivayu-mark-64.png 1x, /nitivayu-mark.png 2x"
                alt="Nitivayu logo"
                width={32}
                height={32}
                className="h-8 w-8 rounded-md"
              />
              <span className="text-base font-medium-plus">Nitivayu</span>
            </p>
            <p className="type-body-md mt-4 text-white/60">
              Helplines close tickets. We solve problems — citizen grievances become
              university-matched, CSR-funded research challenges with enforceable SLAs.
            </p>
            <p className="type-caption mt-6 text-white/40">SIH26043 · Governance & Administration · Jharkhand</p>
          </div>
          <nav className="grid grid-cols-2 gap-8 sm:grid-cols-4" aria-label="Footer">
            {COLS.map((col) => (
              <div key={col.title}>
                <p className="type-caption text-white/40">{col.title}</p>
                <ul className="mt-4 space-y-2.5">
                  {col.links.map(([label, to]) => (
                    <li key={label + to}><Link to={to} className="footer-link">{label}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>
        <div className="mt-14 flex flex-col justify-between gap-3 border-t border-white/15 pt-6 md:flex-row">
          <p className="type-body-sm text-white/60">Built by Team QuantumQuest — empowering citizens, engaging academia, enriching governance.</p>
          <p className="type-body-sm text-white/40">Tracking tokens stay public; accounts stay workspace-scoped.</p>
        </div>
      </div>
    </footer>
  );
}
