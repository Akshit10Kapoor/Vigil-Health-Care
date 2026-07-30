import React from 'react';
import { 
  LayoutDashboard, AlertTriangle, Users, ClipboardList, FileCheck, 
  Pill, FileText, Settings, ChevronLeft, ChevronRight, Shield, Moon, Sun
} from 'lucide-react';

export default function Sidebar({ 
  activeTab, setActiveTab, staff, isCollapsed, setIsCollapsed, theme, toggleTheme 
}) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['admin', 'quality_team', 'ward_manager'] },
    { id: 'gaps', label: 'Gap History', icon: AlertTriangle, roles: ['admin', 'quality_team', 'ward_manager'] },
    { id: 'patients', label: 'Patient Registry', icon: Users, roles: ['admin', 'quality_team', 'ward_manager', 'nurse'] },
    { id: 'rounds', label: 'Nursing Rounds', icon: ClipboardList, roles: ['nurse', 'ward_manager', 'admin'] },
    { id: 'consent', label: 'Informed Consent', icon: FileCheck, roles: ['nurse', 'ward_manager', 'admin'] },
    { id: 'meds', label: 'Medication Orders', icon: Pill, roles: ['nurse', 'ward_manager', 'admin'] },
    { id: 'evidence', label: 'Evidence Export', icon: FileText, roles: ['admin', 'quality_team'] },
    { id: 'settings', label: 'Settings', icon: Settings, roles: ['admin', 'quality_team', 'ward_manager', 'nurse'] },
  ];

  // Filter nav items by staff role
  const userRole = staff?.role || 'nurse';
  const visibleNav = navItems.filter(item => item.roles.includes(userRole));

  return (
    <aside 
      className={`h-screen sticky top-0 bg-[var(--card-bg)] border-r border-[var(--border-subtle)] flex flex-col transition-all duration-200 z-40 select-none ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="p-4 flex items-center justify-between border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-teal)] text-white flex items-center justify-center shrink-0 font-bold shadow-sm">
            <Shield className="w-5 h-5" />
          </div>
          {!isCollapsed && (
            <div className="truncate">
              <h1 className="font-bold text-sm leading-tight text-[var(--text-primary)]">VIGIL</h1>
              <p className="text-[10px] font-mono text-[var(--text-muted)] truncate">CITY CARE HOSPITAL</p>
            </div>
          )}
        </div>
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {visibleNav.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-colors relative ${
                isActive
                  ? 'bg-[var(--accent-teal-light)] text-[var(--accent-teal)] font-semibold'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--card-hover)] hover:text-[var(--text-primary)]'
              }`}
              title={isCollapsed ? item.label : undefined}
            >
              {isActive && (
                <div className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-[var(--accent-teal)] rounded-r" />
              )}
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[var(--accent-teal)]' : 'text-[var(--text-muted)]'}`} />
              {!isCollapsed && <span className="truncate">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Footer Controls: Theme Toggle & Sidebar Collapse */}
      <div className="p-3 border-t border-[var(--border-subtle)] space-y-2">
        <button
          onClick={toggleTheme}
          className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--card-hover)] transition"
          title="Toggle Light/Dark Theme"
        >
          <div className="flex items-center gap-3">
            {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-500" />}
            {!isCollapsed && <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </div>
        </button>

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="w-full flex items-center justify-center p-2 rounded-lg text-[var(--text-muted)] hover:bg-[var(--card-hover)] transition"
          title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>
    </aside>
  );
}
