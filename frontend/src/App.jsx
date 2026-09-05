import React, { Suspense } from 'react';
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { AuthProvider, RequireWorkspace, useAuth } from './lib/auth';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import LandingPage from './components/LandingPage';
import LiveTrackingCard from './components/LiveTrackingCard';
import TrackLanding from './components/TrackLanding';
import HowItWorks from './components/HowItWorks';
import Impact from './components/Impact';
import About from './components/About';
import Login from './components/Login';
import Signup from './components/Signup';

// Workspace shells — lazy-loaded per workspace so a citizen never downloads
// the Officer Console bundle and vice versa (nitivayu.md §4.1).
const CitizenLayout = React.lazy(() => import('./app/citizen/CitizenLayout'));
const CitizenReport = React.lazy(() => import('./app/citizen/CitizenReport'));
const CitizenMyReports = React.lazy(() => import('./app/citizen/CitizenMyReports'));
const CitizenTrack = React.lazy(() => import('./app/citizen/CitizenTrack'));
const CitizenProfile = React.lazy(() => import('./app/citizen/CitizenProfile'));

const OfficerLayout = React.lazy(() => import('./app/officer/OfficerLayout'));

const UniversityLayout = React.lazy(() => import('./app/university/UniversityLayout'));

const CorporateLayout = React.lazy(() => import('./app/corporate/CorporateLayout'));

const AdminLayout = React.lazy(() => import('./app/admin/AdminLayout'));

function WorkspaceFallback() {
  return (
    <div className="mx-auto max-w-content space-y-3 p-6" aria-label="Loading workspace">
      <div className="card h-12 animate-pulse" />
      <div className="card h-64 animate-pulse" />
    </div>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-content px-4 py-20 text-center md:px-6">
      <p className="type-caption text-primary">404</p>
      <h1 className="type-display-md mt-3">This page is not on the map.</h1>
      <p className="type-body-md mt-3 text-zinc-500">Check the address, or start from a place we know.</p>
      <Link to="/" className="btn-primary mt-6 inline-block">Back home</Link>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <div className="flex min-h-screen flex-col bg-white">
        <Navbar />
        <main className="flex-1">
          <Suspense fallback={<WorkspaceFallback />}>
            <Routes>
              {/* Public surface — no login, fast on 3G */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/track" element={<TrackLanding />} />
              <Route path="/track/:token" element={<LiveTrackingCard />} />
              <Route path="/how-it-works" element={<HowItWorks />} />
              <Route path="/impact" element={<Impact />} />
              <Route path="/about" element={<About />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />

              {/* Citizen App */}
              <Route path="/app/citizen" element={<RequireWorkspace allow={['citizen', 'admin']}><CitizenLayout /></RequireWorkspace>}>
                <Route index element={<Navigate to="report" replace />} />
                <Route path="report" element={<CitizenReport />} />
                <Route path="reports" element={<CitizenMyReports />} />
                <Route path="track" element={<CitizenTrack />} />
                <Route path="profile" element={<CitizenProfile />} />
              </Route>

              {/* Officer Console */}
              <Route path="/app/officer" element={<RequireWorkspace allow={['officer', 'admin']}><OfficerLayout /></RequireWorkspace>}>
                <Route index element={<OfficerRoute page="queue" />} />
                <Route path="batch" element={<OfficerRoute page="batch" />} />
                <Route path="escalations" element={<OfficerRoute page="escalations" />} />
              </Route>

              {/* University Workspace */}
              <Route path="/app/university" element={<RequireWorkspace allow={['university', 'admin']}><UniversityLayout /></RequireWorkspace>}>
                <Route index element={<UniversityRoute page="inbox" />} />
                <Route path="projects" element={<UniversityRoute page="projects" />} />
                <Route path="profile" element={<UniversityRoute page="profile" />} />
              </Route>

              {/* Corporate / CSR Workspace */}
              <Route path="/app/corporate" element={<RequireWorkspace allow={['corporate', 'admin']}><CorporateLayout /></RequireWorkspace>}>
                <Route index element={<CorporateRoute page="opportunities" />} />
                <Route path="portfolio" element={<CorporateRoute page="portfolio" />} />
                <Route path="impact" element={<CorporateRoute page="impact" />} />
              </Route>

              {/* Admin Control Plane */}
              <Route path="/app/admin" element={<RequireWorkspace allow={['admin']}><AdminLayout /></RequireWorkspace>}>
                <Route index element={<AdminRoute page="orgs" />} />
                <Route path="telemetry" element={<AdminRoute page="telemetry" />} />
                <Route path="exports" element={<AdminRoute page="exports" />} />
              </Route>

              {/* Legacy routes → workspace homes (demo bookmarks keep working) */}
              <Route path="/report" element={<Navigate to="/app/citizen/report" replace />} />
              <Route path="/officer" element={<Navigate to="/app/officer" replace />} />
              <Route path="/officer/batch" element={<Navigate to="/app/officer/batch" replace />} />
              <Route path="/university" element={<Navigate to="/app/university" replace />} />
              <Route path="/csr" element={<Navigate to="/app/corporate" replace />} />
              <Route path="/dashboard" element={<Navigate to="/app/admin/telemetry" replace />} />

              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </main>
        <AppFooter />
      </div>
    </AuthProvider>
  );
}

/**
 * Public pages get the full marketing sitemap footer.
 * Authenticated workspaces get a minimal utility bar instead —
 * the public footer must never render inside /app/*.
 */
function AppFooter() {
  const { pathname } = useLocation();
  const { session } = useAuth();
  if (!pathname.startsWith('/app/')) return <Footer />;
  const names = {
    citizen: 'Citizen App',
    officer: 'Officer Console',
    university: 'University Workspace',
    corporate: 'Corporate Workspace',
    admin: 'Admin Control Plane',
  };
  const ws = pathname.split('/')[2] || '';
  return (
    <div className="border-t border-border bg-white">
      <div className="mx-auto flex max-w-content flex-wrap items-center justify-between gap-2 px-4 py-3 md:px-6">
        <p className="text-xs text-zinc-500">
          {names[ws] || 'Workspace'}{session?.orgName ? ` · ${session.orgName}` : ''}
        </p>
        <p className="flex items-center gap-4 text-xs text-zinc-500">
          <span>Nitivayu v0.1</span>
          <Link to="/about#contact" className="hover:text-ink">Support</Link>
        </p>
      </div>
    </div>
  );
}

// Route splitters keep each workspace bundle separate (React.lazy boundaries).
function OfficerRoute({ page }) {
  const [Mod, setMod] = React.useState(null);
  React.useEffect(() => { import('./app/officer/OfficerPages').then(setMod); }, []);
  if (!Mod) return <WorkspaceFallback />;
  if (page === 'batch') return <Mod.OfficerBatchPage />;
  if (page === 'escalations') return <Mod.OfficerEscalationsPage />;
  return <Mod.OfficerQueuePage />;
}

function UniversityRoute({ page }) {
  const [Mod, setMod] = React.useState(null);
  React.useEffect(() => { import('./app/university/UniversityPages').then(setMod); }, []);
  if (!Mod) return <WorkspaceFallback />;
  if (page === 'projects') return <Mod.UniversityProjectsPage />;
  if (page === 'profile') return <Mod.UniversityProfilePage />;
  return <Mod.UniversityInboxPage />;
}

function CorporateRoute({ page }) {
  const [Mod, setMod] = React.useState(null);
  React.useEffect(() => { import('./app/corporate/CorporatePages').then(setMod); }, []);
  if (!Mod) return <WorkspaceFallback />;
  if (page === 'portfolio') return <Mod.CorporatePortfolioPage />;
  if (page === 'impact') return <Mod.CorporateImpactPage />;
  return <Mod.CorporateOpportunitiesPage />;
}

function AdminRoute({ page }) {
  const [Mod, setMod] = React.useState(null);
  React.useEffect(() => { import('./app/admin/AdminPages').then(setMod); }, []);
  if (!Mod) return <WorkspaceFallback />;
  if (page === 'telemetry') return <Mod.AdminTelemetryPage />;
  if (page === 'exports') return <Mod.AdminExportsPage />;
  return <Mod.AdminOrgsPage />;
}
