import React from 'react';
import { useAuth } from '../../lib/auth';

export default function CitizenProfile() {
  const { session, logout } = useAuth();
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="type-display-md !text-3xl">Profile</h1>
      <div className="card mt-5 space-y-3 p-6">
        <Row k="Role" v="Citizen reporter" />
        <Row k="Identity" v={session?.orgName || session?.role || 'Verified account'} />
        <Row k="Notifications" v="SMS + tracker updates on every status change" />
        <Row k="Privacy" v="Phone/Aadhaar redacted before AI; photo GPS stripped before storage" />
        <button type="button" onClick={logout} className="btn-secondary mt-2">Sign out</button>
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between gap-6 border-b border-border pb-3 last:border-0 last:pb-0">
      <dt className="type-label-sm text-zinc-500">{k}</dt>
      <dd className="text-right text-sm text-ink">{v}</dd>
    </div>
  );
}
