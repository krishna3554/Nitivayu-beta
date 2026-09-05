import React from 'react';
import { Outlet } from 'react-router-dom';
import { Compass, Wallet, BarChart3 } from 'lucide-react';
import { AppShell } from '../../components/ui';
import { useAuth } from '../../lib/auth';

export default function CorporateLayout() {
  const { session } = useAuth();
  return (
    <AppShell
      workspace="corporate"
      orgLabel={session?.orgName || 'CSR desk'}
      items={[
        { to: '/app/corporate', match: '/app/corporate$', label: 'Opportunities', icon: Compass },
        { to: '/app/corporate/portfolio', match: '/app/corporate/portfolio', label: 'Portfolio', icon: Wallet },
        { to: '/app/corporate/impact', match: '/app/corporate/impact', label: 'Impact reports', icon: BarChart3 },
      ]}
    >
      <Outlet />
    </AppShell>
  );
}
