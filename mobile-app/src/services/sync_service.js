import { 
  getPendingEvents, updateEventSyncStatus, setCachedMetadata, getCachedMetadata 
} from './local_db';
import { getStoredToken } from './auth_service';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export async function syncPendingEvents() {
  const pending = await getPendingEvents();
  if (!pending || pending.length === 0) {
    return { total: 0, synced: 0, failed: 0 };
  }

  const token = getStoredToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Format events payload for batch ingestion
  const payload = {
    events: pending.map(item => ({
      client_sync_id: item.client_sync_id,
      event_id: item.event_id,
      event_type: item.event_type,
      patient_id: item.patient_id,
      ward_id: item.ward_id,
      bed_number: item.bed_number,
      staff_id: item.staff_id,
      device_timestamp: item.device_timestamp,
      device_tz_offset: item.device_tz_offset || '+05:30',
      payload: item.payload,
      raw_note: item.raw_note,
      metadata: item.metadata
    }))
  };

  try {
    const res = await fetch(`${API_BASE_URL}/events/ingest`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`Server returned HTTP ${res.status}`);
    }

    const data = await res.json();
    let synced = 0;
    let failed = 0;

    for (const result of data.results) {
      if (result.status === 'success' || result.status === 'duplicate') {
        await updateEventSyncStatus(result.client_sync_id, 'synced');
        synced++;
      } else {
        await updateEventSyncStatus(result.client_sync_id, 'failed', result.error_message);
        failed++;
      }
    }

    return { total: pending.length, synced, failed };

  } catch (error) {
    console.warn('Sync failed (offline or network error):', error.message);
    return { total: pending.length, synced: 0, failed: pending.length, error: error.message };
  }
}

export async function fetchAndCacheWardsAndPatients() {
  try {
    const wardsRes = await fetch(`${API_BASE_URL}/wards`);
    if (wardsRes.ok) {
      const wards = await wardsRes.json();
      await setCachedMetadata('wards', wards);
    }

    const patRes = await fetch(`${API_BASE_URL}/patients`);
    if (patRes.ok) {
      const patients = await patRes.json();
      await setCachedMetadata('patients', patients);
    }
  } catch (err) {
    console.log('Using offline cached wards and patients');
  }

  const wards = await getCachedMetadata('wards') || [
    { ward_id: 'ICU_01', name: 'Intensive Care Unit (ICU)', acuity_level: 'high' },
    { ward_id: 'SURG_3A', name: 'Surgical Ward 3A', acuity_level: 'medium' },
    { ward_id: 'GEN_2B', name: 'General Ward 2B', acuity_level: 'low' }
  ];

  const patients = await getCachedMetadata('patients') || [
    { patient_id: 'PAT_1001', full_name: 'Ramesh Verma', bed_number: 'Bed-01', ward_id: 'ICU_01' },
    { patient_id: 'PAT_1002', full_name: 'Sunita Devi', bed_number: 'Bed-03', ward_id: 'ICU_01' },
    { patient_id: 'PAT_2001', full_name: 'Vikram Singh', bed_number: 'Bed-3A-05', ward_id: 'SURG_3A' }
  ];

  return { wards, patients };
}
