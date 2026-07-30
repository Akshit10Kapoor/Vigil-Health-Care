import React from 'react';
import { RefreshCcw, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function SyncBar({ pendingCount, isSyncing, onSyncTrigger, lastSyncResult, isOnline }) {
  if (pendingCount === 0 && !lastSyncResult) return null;

  return (
    <div className={`px-4 py-2.5 text-sm font-medium flex items-center justify-between border-b ${
      !isOnline
        ? 'bg-amber-950/40 border-amber-800/50 text-amber-200'
        : pendingCount > 0
        ? 'bg-indigo-950/40 border-indigo-800/50 text-indigo-200'
        : 'bg-emerald-950/40 border-emerald-800/50 text-emerald-200'
    }`}>
      <div className="flex items-center gap-2 max-w-4xl mx-auto w-full justify-between">
        <div className="flex items-center gap-2">
          {!isOnline ? (
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          ) : pendingCount > 0 ? (
            <RefreshCcw className={`w-4 h-4 text-indigo-400 ${isSyncing ? 'animate-spin' : ''}`} />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          )}

          <span>
            {!isOnline
              ? `Airplane mode / Offline: ${pendingCount} clinical events queued in IndexedDB.`
              : pendingCount > 0
              ? `${pendingCount} event(s) waiting to sync to server.`
              : `All events synced successfully.`}
          </span>
        </div>

        {isOnline && pendingCount > 0 && (
          <button
            onClick={onSyncTrigger}
            disabled={isSyncing}
            className="btn btn-primary py-1 px-3 text-xs"
          >
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </button>
        )}
      </div>
    </div>
  );
}
