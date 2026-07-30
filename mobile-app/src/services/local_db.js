import { openDB } from 'idb';

const DB_NAME = 'vigil_offline_db';
const DB_VERSION = 1;

export async function initLocalDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      // 1. Queued Events Store
      if (!db.objectStoreNames.contains('queued_events')) {
        const eventStore = db.createObjectStore('queued_events', { keyPath: 'client_sync_id' });
        eventStore.createIndex('sync_status', 'sync_status', { unique: false });
        eventStore.createIndex('created_at', 'created_at', { unique: false });
      }

      // 2. Auth Session Store
      if (!db.objectStoreNames.contains('session')) {
        db.createObjectStore('session');
      }

      // 3. Cached Metadata Store (Patients & Wards for offline forms)
      if (!db.objectStoreNames.contains('metadata_cache')) {
        db.createObjectStore('metadata_cache');
      }
    },
  });
}

// Queue an event for sync
export async function queueEvent(eventData) {
  const db = await initLocalDB();
  const record = {
    client_sync_id: eventData.client_sync_id || `sync_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    ...eventData,
    sync_status: 'pending', // 'pending', 'synced', 'failed'
    created_at: new Date().toISOString(),
    error_message: null
  };
  await db.put('queued_events', record);
  return record;
}

// Get all queued events
export async function getQueuedEvents() {
  const db = await initLocalDB();
  return await db.getAll('queued_events');
}

// Get pending events for sync
export async function getPendingEvents() {
  const db = await initLocalDB();
  const all = await db.getAll('queued_events');
  return all.filter(e => e.sync_status === 'pending');
}

// Update single event status
export async function updateEventSyncStatus(client_sync_id, status, errorMessage = null) {
  const db = await initLocalDB();
  const item = await db.get('queued_events', client_sync_id);
  if (item) {
    item.sync_status = status;
    item.error_message = errorMessage;
    if (status === 'synced') {
      item.synced_at = new Date().toISOString();
    }
    await db.put('queued_events', item);
  }
}

// Cache patients & wards offline
export async function setCachedMetadata(key, value) {
  const db = await initLocalDB();
  await db.put('metadata_cache', value, key);
}

export async function getCachedMetadata(key) {
  const db = await initLocalDB();
  return await db.get('metadata_cache', key);
}
