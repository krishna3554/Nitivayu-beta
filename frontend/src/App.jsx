import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Bell } from 'lucide-react';
import CitizenIntakeForm from './components/CitizenIntakeForm';
import LiveTrackingCard from './components/LiveTrackingCard';
import OfficerReviewQueue from './components/OfficerReviewQueue';
import BatchTriageControl from './components/BatchTriageControl';
import UniversityPortal from './components/UniversityPortal';
import CSRFundingPortal from './components/CSRFundingPortal';
import ScalabilityDashboard from './components/ScalabilityDashboard';
import Login from './components/Login';
import LandingPage from './components/LandingPage';
import NotFound from './components/NotFound';

const NAV_LINKS = [
  { to: '/report', label: 'Report' },
  { to: '/track', label: 'Track' },
  { to: '/officer', label: 'Officer' },
  { to: '/officer/batch', label: 'Batch' },
  { to: '/university', label: 'University' },
  { to: '/csr', label: 'CSR' },
  { to: '/dashboard', label: 'Dashboard' },
];

function Navbar() {
  const location = useLocation();
  return (
    <nav className="bg-white border-b border-zinc-200 px-4 py-3 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-6 min-w-0">
          <Link to="/" className="text-xl font-bold text-zinc-900 flex items-center gap-2 shrink-0">
            <div className="w-8 h-8 bg-indigo-600 rounded flex items-center justify-center text-white">N</div>
            Nitivayu
          </Link>
          <div className="hidden md:flex items-center gap-4 text-sm font-medium text-zinc-600">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`hover:text-zinc-900 transition-colors ${location.pathname === link.to ? 'text-indigo-700 font-semibold' : ''}`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <button className="text-zinc-500 hover:text-zinc-900 p-2 relative" aria-label="Notifications">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-600 rounded-full"></span>
          </button>
          <Link to="/login" className="text-sm font-medium px-4 py-2 bg-zinc-900 text-white rounded-md hover:bg-zinc-800 transition-colors">
            Login
          </Link>
        </div>
      </div>
      <div className="md:hidden mt-2 flex gap-3 overflow-x-auto text-sm font-medium text-zinc-600 pb-1">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={`whitespace-nowrap hover:text-zinc-900 ${location.pathname === link.to ? 'text-indigo-700 font-semibold' : ''}`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

function App() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/report" element={<CitizenIntakeForm />} />
          <Route path="/track" element={<LiveTrackingCard />} />
          <Route path="/track/:token" element={<LiveTrackingCard />} />
          <Route path="/officer" element={<OfficerReviewQueue />} />
          <Route path="/officer/batch" element={<BatchTriageControl />} />
          <Route path="/university" element={<UniversityPortal />} />
          <Route path="/csr" element={<CSRFundingPortal />} />
          <Route path="/dashboard" element={<ScalabilityDashboard />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
