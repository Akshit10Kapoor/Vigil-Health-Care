import React from 'react';
import { Search, Bell, Wifi, WifiOff, LogOut, Command, ShieldCheck } from 'lucide-react';

export default function TopBar({ 
  activeTab, staff, onLogout, onOpenCommandPalette, isOnline, pendingCount, unreadAlertsCount 
}) {
  const getBreadcrumbTitle = () => {
    switch (activeTab) {
      case 'dashboard': return 'Quality Dashboard · Ward Overview';
      case 'gaps': return 'Clinical Compliance · Gap History';
      case 'patients': return 'Patient Registry · Audit Timelines';
      case 'rounds': return 'Clinical Action Capture · Nursing Round Checklist';
      case 'consent': return 'Clinical Action Capture · Informed Consent Verification';
      case 'meds': return 'Clinical Action Capture · Medication Order Administration';
      case 'evidence': return 'NABH Audit Compliance · Evidence Export';
      case 'settings': return 'Hospital Operations · Settings';
      case 'sync': return 'Offline Engine · Queue Inspector';
      default: return 'Vigil Clinical Action Verification';
    }
  };

  return (
    <header className="h-14 bg-[var(--card-bg)] border-b border-[var(--border-subtle)] px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Left: Breadcrumbs */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-[var(--text-secondary)] font-mono uppercase tracking-wider">VIGIL</span>
        <span className="text-xs text-[var(--text-muted)]">/</span>
        <h2 className="text-xs font-medium text-[var(--text-primary)] font-mono">{getBreadcrumbTitle()}</h2>
      </div>

      {/* Right: Command Palette Trigger, Status, Bell & User Session */}
      <div className="flex items-center gap-4">
        {/* Command Palette Trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-[var(--canvas-bg)] border border-[var(--border-medium)] rounded-md text-xs text-[var(--text-secondary)] hover:border-[var(--accent-teal)] transition"
        >
          <Search className="w-3.5 h-3.5 text-[var(--text-muted)]" />
          <span>Search or jump to...</span>
          <kbd className="flex items-center gap-0.5 px-1.5 py-0.5 bg-[var(--card-bg)] border border-[var(--border-subtle)] rounded text-[10px] font-mono text-[var(--text-muted)] shadow-2xs">
            <Command className="w-2.5 h-2.5" /> K
          </kbd>
        </button>

        {/* Network Online/Offline Status */}
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium ${
          isOnline
            ? 'bg-[var(--severity-resolved-bg)] text-[var(--severity-resolved-color)] border border-[var(--severity-resolved-border)]'
            : 'bg-[var(--severity-routine-bg)] text-[var(--severity-routine-color)] border border-[var(--severity-routine-border)]'
        }`}>
          {isOnline ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          <span>{isOnline ? 'ONLINE' : `OFFLINE (${pendingCount})`}</span>
        </div>

        {/* Notification Bell */}
        <div className="relative">
          <button 
            className="p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--card-hover)] rounded-lg transition relative"
            title="Notifications Feed"
          >
            <Bell className="w-4 h-4" />
            {unreadAlertsCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-[var(--severity-urgent-color)] rounded-full animate-ping" />
            )}
            {unreadAlertsCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 bg-[var(--severity-urgent-color)] rounded-full" />
            )}
          </button>
        </div>

        {/* Staff Profile & Logout */}
        {staff && (
          <div className="flex items-center gap-3 pl-3 border-l border-[var(--border-subtle)]">
            <div className="text-right">
              <p className="text-xs font-semibold text-[var(--text-primary)]">{staff.full_name}</p>
              <p className="text-[10px] font-mono text-[var(--text-muted)] uppercase">{staff.role}</p>
            </div>
            <button
              onClick={onLogout}
              className="p-1.5 text-[var(--text-muted)] hover:text-[var(--severity-urgent-color)] hover:bg-[var(--severity-urgent-bg)] rounded-md transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
