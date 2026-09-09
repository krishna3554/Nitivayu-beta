import React, { useEffect, useState } from 'react';
import { useAuth } from '../../lib/auth';
import { getMe, updateMe } from '../../services/api';
import { fetchMetaConfig } from '../../lib/meta';

export default function CitizenProfile() {
  const { session, logout } = useAuth();
  const [me, setMe] = useState(null);
  const [form, setForm] = useState({ display_name: '', district: '', language_pref: '', notify_sms: false });
  const [districts, setDistricts] = useState([]);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let live = true;
    getMe().then(({ data }) => {
      if (!live) return;
      setMe(data);
      setForm({
        display_name: data.display_name || '',
        district: data.district || '',
        language_pref: data.language_pref || '',
        notify_sms: Boolean(data.notify_sms),
      });
    }).catch(() => {});
    fetchMetaConfig().then((c) => { if (live && c.districts?.length) setDistricts(c.districts); });
    return () => { live = false; };
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setNotice('');
    try {
      await updateMe({
        display_name: form.display_name || undefined,
        district: form.district || undefined,
        language_pref: form.language_pref || undefined,
        notify_sms: form.notify_sms,
      });
      setNotice('Profile saved.');
    } catch (err) { setNotice(err.response?.data?.detail || 'Could not save your profile.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="type-display-md !text-3xl">Profile</h1>
      <div className="card mt-5 space-y-3 p-6">
        <Row k="Role" v={me?.role ? `${me.role} reporter` : 'Citizen reporter'} />
        <Row k="Identity" v={me?.display_name || session?.displayName || session?.orgName || 'Verified account'} />
        {me?.organization_name && <Row k="Organization" v={me.organization_name} />}
        <Row k="Privacy" v="Phone/Aadhaar redacted before AI; photo GPS stripped before storage" />
      </div>

      <form onSubmit={save} className="card mt-4 space-y-4 p-6">
        <h2 className="font-medium-plus">Preferences</h2>
        <label className="type-label-sm block">Display name
          <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="How officers see you" className="input mt-1.5" />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="type-label-sm block">District
            <select value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} className="input mt-1.5">
              <option value="">—</option>
              {districts.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label className="type-label-sm block">Language
            <select value={form.language_pref} onChange={(e) => setForm({ ...form, language_pref: e.target.value })} className="input mt-1.5">
              <option value="">—</option>
              <option value="hindi">Hindi</option>
              <option value="hinglish">Hinglish</option>
              <option value="english">English</option>
            </select>
          </label>
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={form.notify_sms} onChange={(e) => setForm({ ...form, notify_sms: e.target.checked })} className="mt-1" />
          <span>Text me on status changes <span className="text-zinc-500">(SMS when your issue is accepted or a milestone verifies)</span></span>
        </label>
        {notice && <p className="text-sm text-zinc-500">{notice}</p>}
        <div className="flex items-center gap-2">
          <button type="submit" disabled={saving} className="btn-primary !py-2 disabled:opacity-60">{saving ? 'Saving…' : 'Save preferences'}</button>
          <button type="button" onClick={logout} className="btn-secondary !py-2">Sign out</button>
        </div>
      </form>
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
