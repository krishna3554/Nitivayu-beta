import React from 'react';
import { Outlet } from 'react-router-dom';
import { FilePlus2, FolderOpen, Radar, User } from 'lucide-react';
import { AppShell } from '../../components/ui';
import { useAuth } from '../../lib/auth';

export default function CitizenLayout() {
  const { session } = useAuth();
  const myCount = (() => { try { return (JSON.parse(localStorage.getItem('nitivayu_my_reports') || '[]') || []).length; } catch { return 0; } })();
  return (
    <AppShell
      workspace="citizen"
      orgLabel={session?.orgName || 'Resident reporter'}
      items={[
        { to: '/app/citizen/report', match: '/app/citizen/report', label: 'Report', icon: FilePlus2 },
        { to: '/app/citizen/reports', match: '/app/citizen/reports', label: 'My reports', icon: FolderOpen, badge: myCount || undefined },
        { to: '/app/citizen/track', match: '/app/citizen/track', label: 'Track', icon: Radar },
        { to: '/app/citizen/profile', match: '/app/citizen/profile', label: 'Profile', icon: User },
      ]}
    >
      <Outlet />
    </AppShell>
  );
}
