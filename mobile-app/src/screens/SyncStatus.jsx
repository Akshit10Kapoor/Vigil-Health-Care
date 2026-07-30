import React from 'react';
import { RefreshCw, CheckCircle2, Clock, AlertTriangle, Database } from 'lucide-react';

export default function SyncStatus({ queuedEvents, isSyncing, onManualSync, isOnline }) {
  const pendingItems = queuedEvents.filter(e => e.sync_status === 'pending');
  const syncedItems = queuedEvents.filter(e => e.sync_status === 'synced');
  const failedItems = queuedEvents.filter(e => e.sync_status === 'failed');

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-indigo-400" />
            <span>IndexedDB Offline Queue & Sync Status</span>
          </h2>
          <p className="text-sm text-slate-400">Inspect local event queue, itemized sync state, and retry failed events</p>
        </div>

        <button
          onClick={onManualSync}
          disabled={isSyncing || pendingItems.length === 0}
          className="btn btn-primary py-2.5 px-4 text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
          <span>{isSyncing ? 'Syncing Queue...' : 'Force Sync Queue Now'}</span>
        </button>
      </div>

      {/* Counter Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card border-amber-900/50 bg-amber-950/20 text-center p-4">
          <Clock className="w-6 h-6 mx-auto mb-1 text-amber-400" />
          <span className="text-2xl font-extrabold text-amber-300">{pendingItems.length}</span>
          <p className="text-xs font-semibold text-amber-400/80 uppercase tracking-wider">Pending Sync</p>
        </div>

        <div className="card border-emerald-900/50 bg-emerald-950/20 text-center p-4">
          <CheckCircle2 className="w-6 h-6 mx-auto mb-1 text-emerald-400" />
          <span className="text-2xl font-extrabold text-emerald-300">{syncedItems.length}</span>
          <p className="text-xs font-semibold text-emerald-400/80 uppercase tracking-wider">Synced to Server</p>
        </div>

        <div className="card border-rose-900/50 bg-rose-950/20 text-center p-4">
          <AlertTriangle className="w-6 h-6 mx-auto mb-1 text-rose-400" />
          <span className="text-2xl font-extrabold text-rose-300">{failedItems.length}</span>
          <p className="text-xs font-semibold text-rose-400/80 uppercase tracking-wider">Failed Items</p>
        </div>
      </div>

      {/* Events List */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Local Event Log ({queuedEvents.length})</h3>

        {queuedEvents.length === 0 ? (
          <div className="text-center py-10 text-slate-500">
            <Database className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p>No events logged in IndexedDB yet.</p>
            <p className="text-xs mt-1">Logged rounds, consents, and med orders will appear here.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {queuedEvents.map((item) => (
              <div key={item.client_sync_id} className="py-3.5 flex flex-wrap items-center justify-between gap-3 text-sm">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-200 capitalize">
                      {item.event_type.replace('_', ' ')}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      Patient: {item.patient_id} ({item.ward_id})
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    Sync ID: {item.client_sync_id} · Time: {new Date(item.device_timestamp).toLocaleString()}
                  </div>
                  {item.error_message && (
                    <div className="text-xs text-rose-400 mt-1 font-mono">
                      Error: {item.error_message}
                    </div>
                  )}
                </div>

                <div>
                  {item.sync_status === 'pending' && (
                    <span className="badge badge-offline">
                      <Clock className="w-3 h-3" /> PENDING
                    </span>
                  )}
                  {item.sync_status === 'synced' && (
                    <span className="badge badge-online">
                      <CheckCircle2 className="w-3 h-3" /> SYNCED
                    </span>
                  )}
                  {item.sync_status === 'failed' && (
                    <span className="badge bg-rose-950 text-rose-400 border border-rose-800">
                      <AlertTriangle className="w-3 h-3" /> FAILED
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
