import React from 'react';
import { Outlet } from 'react-router-dom';
import { Inbox, KanbanSquare, CircleUser } from 'lucide-react';
import { AppShell } from '../../components/ui';
import { useAuth } from '../../lib/auth';

export default function UniversityLayout() {
  const { session } = useAuth();
  return (
    <AppShell
      workspace="university"
      orgLabel={session?.orgName || 'IIC workspace'}
      items={[
        { to: '/app/university', match: '/app/university$', label: 'Challenge inbox', icon: Inbox },
        { to: '/app/university/projects', match: '/app/university/projects', label: 'Active projects', icon: KanbanSquare },
        { to: '/app/university/profile', match: '/app/university/profile', label: 'IIC profile', icon: CircleUser },
      ]}
    >
      <Outlet />
    </AppShell>
  );
}
