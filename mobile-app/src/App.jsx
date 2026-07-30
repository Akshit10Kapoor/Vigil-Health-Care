import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import CommandPalette from './components/CommandPalette';
import SyncBar from './components/SyncBar';
import Login from './screens/Login';

import DashboardOverview from './screens/DashboardOverview';
import GapHistoryTable from './screens/GapHistoryTable';
import PatientRegistry from './screens/PatientRegistry';
import RoundChecklist from './screens/RoundChecklist';
import ConsentCapture from './screens/ConsentCapture';
import MedOrderLog from './screens/MedOrderLog';
import EvidenceExportView from './screens/EvidenceExportView';
import SettingsView from './screens/SettingsView';
import SyncStatus from './screens/SyncStatus';

import { getStoredStaff, logoutStaff } from './services/auth_service';
import { getQueuedEvents } from './services/local_db';
import { syncPendingEvents, fetchAndCacheWardsAndPatients } from './services/sync_service';

export default function App() {
  const [staff, setStaff] = useState(getStoredStaff());
  const [activeTab, setActiveTab] = useState(staff?.role === 'nurse' ? 'rounds' : 'dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState(localStorage.getItem('vigil_theme') || 'light');
  
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [queuedEvents, setQueuedEvents] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSyncResult, setLastSyncResult] = useState(null);

  const [wards, setWards] = useState([]);
  const [patients, setPatients] = useState([]);

  // Theme effect
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('vigil_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  const refreshQueue = async () => {
    const events = await getQueuedEvents();
    setQueuedEvents(events.reverse());
  };

  useEffect(() => {
    refreshQueue();

    const handleOnline = () => {
      setIsOnline(true);
      handleSync();
    };

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    fetchAndCacheWardsAndPatients().then(({ wards, patients }) => {
      setWards(wards);
      setPatients(patients);
    });

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleSync = async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    const result = await syncPendingEvents();
    setLastSyncResult(result);
    setIsSyncing(false);
    await refreshQueue();
  };

  const handleEventQueued = async () => {
    await refreshQueue();
    if (isOnline) {
      handleSync();
    }
  };

  const handleLogout = () => {
    logoutStaff();
    setStaff(null);
  };

  const handleCommandNavigate = (targetTab) => {
    setActiveTab(targetTab);
  };

  if (!staff) {
    return <Login onLoginSuccess={(user) => {
      setStaff(user);
      setActiveTab(user.role === 'nurse' ? 'rounds' : 'dashboard');
    }} />;
  }

  const pendingCount = queuedEvents.filter(e => e.sync_status === 'pending').length;

  return (
    <div className="flex min-h-screen bg-[var(--canvas-bg)] text-[var(--text-primary)]">
      {/* Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        staff={staff}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
        theme={theme}
        toggleTheme={toggleTheme}
      />

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          activeTab={activeTab}
          staff={staff}
          onLogout={handleLogout}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          isOnline={isOnline}
          pendingCount={pendingCount}
          unreadAlertsCount={1}
        />

        <SyncBar
          pendingCount={pendingCount}
          isSyncing={isSyncing}
          onSyncTrigger={handleSync}
          lastSyncResult={lastSyncResult}
          isOnline={isOnline}
        />

        <main className="flex-1 p-6 overflow-y-auto max-w-7xl w-full mx-auto">
          {activeTab === 'dashboard' && (
            <DashboardOverview
              wards={wards}
              queuedEvents={queuedEvents}
              onSelectWard={() => setActiveTab('gaps')}
              onOpenGapDetail={() => setActiveTab('gaps')}
            />
          )}

          {activeTab === 'gaps' && (
            <GapHistoryTable
              queuedEvents={queuedEvents}
              wards={wards}
              onAcknowledgeGap={(gapId) => console.log('Ack gap:', gapId)}
            />
          )}

          {activeTab === 'patients' && (
            <PatientRegistry
              patients={patients}
              queuedEvents={queuedEvents}
            />
          )}

          {activeTab === 'rounds' && (
            <RoundChecklist
              patients={patients}
              wards={wards}
              staff={staff}
              onEventQueued={handleEventQueued}
            />
          )}

          {activeTab === 'consent' && (
            <ConsentCapture
              patients={patients}
              wards={wards}
              staff={staff}
              onEventQueued={handleEventQueued}
            />
          )}

          {activeTab === 'meds' && (
            <MedOrderLog
              patients={patients}
              wards={wards}
              staff={staff}
              onEventQueued={handleEventQueued}
            />
          )}

          {activeTab === 'evidence' && (
            <EvidenceExportView staff={staff} />
          )}

          {activeTab === 'settings' && (
            <SettingsView
              staff={staff}
              wards={wards}
              theme={theme}
              toggleTheme={toggleTheme}
            />
          )}

          {activeTab === 'sync' && (
            <SyncStatus
              queuedEvents={queuedEvents}
              isSyncing={isSyncing}
              onManualSync={handleSync}
              isOnline={isOnline}
            />
          )}
        </main>
      </div>

      {/* Global Command Palette (Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onNavigate={handleCommandNavigate}
        wards={wards}
        patients={patients}
      />
    </div>
  );
}
