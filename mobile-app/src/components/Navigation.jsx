import React from 'react';
import { ClipboardList, FileCheck, Pill, RefreshCw, LogOut, Wifi, WifiOff, ShieldCheck } from 'lucide-react';

export default function Navigation({ activeTab, setActiveTab, staff, onLogout, isOnline, pendingCount }) {
  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
        {/* Brand Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-tr from-indigo-600 to-blue-500 rounded-xl text-white shadow-lg">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-white leading-tight">VIGIL</h1>
            <p className="text-xs text-slate-400 font-medium">Clinical Event Verification</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('rounds')}
            className={`btn py-2 px-3 text-sm rounded-lg ${
              activeTab === 'rounds' ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <ClipboardList className="w-4 h-4" />
            <span className="hidden sm:inline">Rounds</span>
          </button>

          <button
            onClick={() => setActiveTab('consent')}
            className={`btn py-2 px-3 text-sm rounded-lg ${
              activeTab === 'consent' ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <FileCheck className="w-4 h-4" />
            <span className="hidden sm:inline">Consent</span>
          </button>

          <button
            onClick={() => setActiveTab('meds')}
            className={`btn py-2 px-3 text-sm rounded-lg ${
              activeTab === 'meds' ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <Pill className="w-4 h-4" />
            <span className="hidden sm:inline">Med Orders</span>
          </button>

          <button
            onClick={() => setActiveTab('sync')}
            className={`btn py-2 px-3 text-sm rounded-lg relative ${
              activeTab === 'sync' ? 'bg-indigo-600 text-white font-semibold' : 'text-slate-400 hover:text-white hover:bg-slate-900'
            }`}
          >
            <RefreshCw className="w-4 h-4" />
            <span className="hidden sm:inline">Sync Queue</span>
            {pendingCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-amber-500 text-slate-950 font-bold text-xs w-5 h-5 rounded-full flex items-center justify-center shadow">
                {pendingCount}
              </span>
            )}
          </button>
        </nav>

        {/* User Session & Status */}
        <div className="flex items-center gap-3">
          <div className={`badge ${isOnline ? 'badge-online' : 'badge-offline'}`}>
            {isOnline ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            <span>{isOnline ? 'ONLINE' : 'OFFLINE'}</span>
          </div>

          {staff && (
            <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
              <div className="text-right hidden md:block">
                <p className="text-xs font-semibold text-slate-200">{staff.full_name}</p>
                <p className="text-[10px] text-slate-400 uppercase tracking-wider">{staff.role}</p>
              </div>
              <button
                onClick={onLogout}
                title="Logout"
                className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
