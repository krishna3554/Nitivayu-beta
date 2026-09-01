import React from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import CitizenIntakeForm from './components/CitizenIntakeForm';
import LiveTrackingCard from './components/LiveTrackingCard';
import OfficerReviewQueue from './components/OfficerReviewQueue';
import BatchTriageControl from './components/BatchTriageControl';
import UniversityPortal from './components/UniversityPortal';
import CSRFundingPortal from './components/CSRFundingPortal';
import ScalabilityDashboard from './components/ScalabilityDashboard';
import Login from './components/Login';

function Navbar() {
  return (
    <nav className="bg-white border-b border-zinc-200 px-4 py-3 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-6">
        <Link to="/" className="text-xl font-bold text-zinc-900 flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded flex items-center justify-center text-white">N</div>
          Nitivayu
        </Link>
        <div className="hidden md:flex items-center gap-4 text-sm font-medium text-zinc-600">
          <Link to="/officer" className="hover:text-zinc-900">Officer</Link>
          <Link to="/officer/batch" className="hover:text-zinc-900">Batch</Link>
          <Link to="/university" className="hover:text-zinc-900">University</Link>
          <Link to="/csr" className="hover:text-zinc-900">CSR</Link>
          <Link to="/dashboard" className="hover:text-zinc-900">Dashboard</Link>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button className="text-zinc-500 hover:text-zinc-900 p-2 relative">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-600 rounded-full"></span>
        </button>
        <Link to="/login" className="text-sm font-medium px-4 py-2 bg-zinc-900 text-white rounded-md hover:bg-zinc-800 transition-colors">
          Login
        </Link>
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
          <Route path="/" element={<CitizenIntakeForm />} />
          <Route path="/track/:token" element={<LiveTrackingCard />} />
          <Route path="/officer" element={<OfficerReviewQueue />} />
          <Route path="/officer/batch" element={<BatchTriageControl />} />
          <Route path="/university" element={<UniversityPortal />} />
          <Route path="/csr" element={<CSRFundingPortal />} />
          <Route path="/dashboard" element={<ScalabilityDashboard />} />
          <Route path="/login" element={<Login />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
