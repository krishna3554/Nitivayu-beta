import React from 'react';
import { Outlet } from 'react-router-dom';
import { Building2, Activity, FileDown } from 'lucide-react';
import { AppShell } from '../../components/ui';

export default function AdminLayout() {
  return (
    <AppShell
      workspace="admin"
      orgLabel="Control plane"
      items={[
        { to: '/app/admin', match: '/app/admin$', label: 'Organizations', icon: Building2 },
        { to: '/app/admin/telemetry', match: '/app/admin/telemetry', label: 'Telemetry', icon: Activity },
        { to: '/app/admin/exports', match: '/app/admin/exports', label: 'Compliance exports', icon: FileDown },
      ]}
    >
      <Outlet />
    </AppShell>
  );
}
