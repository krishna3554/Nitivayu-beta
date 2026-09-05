import React from 'react';
import { Outlet } from 'react-router-dom';
import { ListChecks, CalendarClock, AlertTriangle } from 'lucide-react';
import { AppShell } from '../../components/ui';
import { useAuth } from '../../lib/auth';

export default function OfficerLayout() {
  const { session } = useAuth();
  return (
    <AppShell
      workspace="officer"
      orgLabel={session?.orgName || 'Nodal verification gate'}
      items={[
        { to: '/app/officer', end: true, label: 'Review queue', icon: ListChecks },
        { to: '/app/officer/batch', label: 'Batch control', icon: CalendarClock },
        { to: '/app/officer/escalations', label: 'Escalations', icon: AlertTriangle },
      ]}
    >
      <Outlet />
    </AppShell>
  );
}
