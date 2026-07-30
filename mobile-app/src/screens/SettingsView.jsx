import React, { useState } from 'react';
import { Settings, Shield, Users, Bell, Moon, Sun, CheckCircle2 } from 'lucide-react';

export default function SettingsView({ staff, wards = [], theme, toggleTheme }) {
  const [activeSubTab, setActiveSubTab] = useState('wards');
  const [saveSuccess, setSaveSuccess] = useState('');

  const isAdmin = staff?.role === 'admin';

  const handleSave = (e) => {
    e.preventDefault();
    setSaveSuccess('Hospital configuration updated successfully.');
    setTimeout(() => setSaveSuccess(''), 3000);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h2 className="text-base font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
          <Settings className="w-4 h-4 text-[var(--accent-teal)]" />
          <span>Hospital Operations & System Settings</span>
        </h2>
        <p className="text-xs text-[var(--text-secondary)] font-mono">Ward definitions, staff accounts, and escalation rules</p>
      </div>

      {saveSuccess && (
        <div className="p-3 bg-[var(--severity-resolved-bg)] border border-[var(--severity-resolved-border)] text-[var(--severity-resolved-color)] rounded-lg flex items-center gap-2 text-xs font-semibold">
          <CheckCircle2 className="w-4 h-4" />
          <span>{saveSuccess}</span>
        </div>
      )}

      {/* Sub Tabs */}
      <div className="flex border-b border-[var(--border-subtle)] space-x-6 text-xs font-mono">
        <button
          onClick={() => setActiveSubTab('wards')}
          className={`pb-2 font-semibold border-b-2 transition ${
            activeSubTab === 'wards' ? 'border-[var(--accent-teal)] text-[var(--accent-teal)]' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          Wards & Protocols
        </button>
        <button
          onClick={() => setActiveSubTab('staff')}
          className={`pb-2 font-semibold border-b-2 transition ${
            activeSubTab === 'staff' ? 'border-[var(--accent-teal)] text-[var(--accent-teal)]' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          Staff & Roles
        </button>
        <button
          onClick={() => setActiveSubTab('theme')}
          className={`pb-2 font-semibold border-b-2 transition ${
            activeSubTab === 'theme' ? 'border-[var(--accent-teal)] text-[var(--accent-teal)]' : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          Theme & Display
        </button>
      </div>

      {/* Wards Tab */}
      {activeSubTab === 'wards' && (
        <div className="card-panel space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] font-mono flex items-center gap-2">
            <Shield className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Configured Hospital Wards ({wards.length})</span>
          </h3>

          <div className="divide-y divide-[var(--border-subtle)] font-mono text-xs">
            {wards.map((w) => (
              <div key={w.ward_id} className="py-3 flex items-center justify-between">
                <div>
                  <p className="font-bold text-[var(--text-primary)]">{w.name} ({w.ward_id})</p>
                  <p className="text-[10px] text-[var(--text-muted)]">Capacity: {w.capacity} Beds · Acuity: {w.acuity_level.toUpperCase()}</p>
                </div>
                <span className="badge-severity badge-resolved">Active</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Staff Tab */}
      {activeSubTab === 'staff' && (
        <div className="card-panel space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] font-mono flex items-center gap-2">
            <Users className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Staff Account Permissions</span>
          </h3>

          <div className="p-3 bg-[var(--canvas-bg)] border border-[var(--border-subtle)] rounded-lg text-xs space-y-1">
            <p className="font-semibold text-[var(--text-primary)]">Logged in as: {staff?.full_name} ({staff?.staff_id})</p>
            <p className="font-mono text-[var(--text-muted)] text-[11px]">Assigned Role: {staff?.role?.toUpperCase()}</p>
          </div>
        </div>
      )}

      {/* Theme Tab */}
      {activeSubTab === 'theme' && (
        <div className="card-panel space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] font-mono flex items-center gap-2">
            <Sun className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Theme Preference</span>
          </h3>

          <div className="flex items-center justify-between p-3 bg-[var(--canvas-bg)] border border-[var(--border-subtle)] rounded-lg text-xs">
            <div>
              <p className="font-semibold text-[var(--text-primary)]">Current Theme: {theme.toUpperCase()}</p>
              <p className="text-[11px] text-[var(--text-muted)] font-mono">Switch between warm-neutral light mode and dark mode</p>
            </div>

            <button onClick={toggleTheme} className="btn-ui btn-ui-secondary text-xs">
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-500" />}
              <span>Switch Theme</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
