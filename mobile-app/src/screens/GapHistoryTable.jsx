import React, { useState, useEffect } from 'react';
import { AlertTriangle, Clock, Info, CheckCircle2, Filter, ChevronRight, Check } from 'lucide-react';
import Drawer from '../components/Drawer';

export default function GapHistoryTable({ queuedEvents, wards, onAcknowledgeGap }) {
  const [severityFilter, setSeverityFilter] = useState('all');
  const [wardFilter, setWardFilter] = useState('all');
  const [selectedGap, setSelectedGap] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const [gapsData, setGapsData] = useState([]);

  useEffect(() => {
    const fetchGaps = async () => {
      try {
        const token = localStorage.getItem('vigil_token');
        const res = await fetch('http://localhost:8000/api/v1/gaps', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const apiGaps = await res.json();
          if (apiGaps.length > 0) {
            // Map backend schema to frontend format
            const formattedGaps = apiGaps.map((g, i) => ({
              gap_id: `gap_api_${i}`,
              severity: (g.severity || 'routine').toLowerCase(),
              ward_id: g.ward_id,
              patient_id: g.patient_id,
              event_type: g.event_type || 'nursing_round',
              expected_time: g.expected_time,
              actual_time: '—',
              status: 'open',
              assigned_to: 'Assigned Staff',
              description: g.description,
              raw_note: 'No note provided',
              model_version: g.model_version
            }));
            setGapsData(formattedGaps);
            return;
          }
        }
      } catch (e) {
        console.error("Failed to fetch API gaps, falling back to mock", e);
      }
      
      // Fallback
      setGapsData([
        {
          gap_id: 'gap_001',
          severity: 'urgent',
          ward_id: 'ICU_01',
          patient_id: 'PAT_1001',
          event_type: 'nursing_round',
          expected_time: '2026-07-30T14:00:00+05:30',
          actual_time: '—',
          status: 'open',
          assigned_to: 'Nurse Anjali Sharma',
          description: 'Missed 2-Hour High-Acuity ICU Vitals Round. Protocol expects vitals log every 120 minutes. Last logged vitals were 155 minutes ago.',
          raw_note: 'Patient was undergoing portable X-ray procedure',
          model_version: 'stub-v1'
        },
        {
          gap_id: 'gap_002',
          severity: 'routine',
          ward_id: 'SURG_3A',
          patient_id: 'PAT_2001',
          event_type: 'consent_capture',
          expected_time: '2026-07-30T10:00:00+05:30',
          actual_time: '2026-07-30T11:15:00+05:30',
          status: 'open',
          assigned_to: 'Nurse Rajesh Kumar',
          description: 'Informed Consent recorded 75 minutes after Central Line order placement. Protocol target is pre-procedure verification within 30 min.',
          raw_note: 'Attending physician was in OT'
        },
        {
          gap_id: 'gap_003',
          severity: 'doc',
          ward_id: 'ICU_01',
          patient_id: 'PAT_1002',
          event_type: 'medication_order_documentation',
          expected_time: '2026-07-30T12:00:00+05:30',
          actual_time: '2026-07-30T12:05:00+05:30',
          status: 'resolved',
          assigned_to: 'Nurse Priya Patel',
          description: 'High-Alert Regular Insulin administration documented with secondary nurse verification.',
          raw_note: 'Dual verification performed with Nurse Anjali Sharma'
        }
      ]);
    };
    fetchGaps();
  }, []);

  const filteredGaps = gapsData.filter(gap => {
    if (severityFilter !== 'all' && gap.severity !== severityFilter) return false;
    if (wardFilter !== 'all' && gap.ward_id !== wardFilter) return false;
    return true;
  });

  const handleRowClick = (gap) => {
    setSelectedGap(gap);
    setIsDrawerOpen(true);
  };

  return (
    <div className="space-y-4">
      {/* Header & Chip Filters */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Clinical Gap History & Audit Log</span>
          </h2>
          <p className="text-xs text-[var(--text-secondary)]">Reconciled expected vs actual clinical event log</p>
        </div>

        {/* Filter Chip Toggles */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-[var(--card-bg)] border border-[var(--border-medium)] rounded-lg p-1 text-xs">
            <Filter className="w-3.5 h-3.5 text-[var(--text-muted)] mx-2" />
            <button
              onClick={() => setSeverityFilter('all')}
              className={`px-2.5 py-1 rounded-md transition ${severityFilter === 'all' ? 'bg-[var(--canvas-bg)] text-[var(--text-primary)] font-semibold' : 'text-[var(--text-secondary)]'}`}
            >
              All Severities
            </button>
            <button
              onClick={() => setSeverityFilter('urgent')}
              className={`px-2.5 py-1 rounded-md transition ${severityFilter === 'urgent' ? 'bg-[var(--severity-urgent-bg)] text-[var(--severity-urgent-color)] font-semibold' : 'text-[var(--text-secondary)]'}`}
            >
              Urgent
            </button>
            <button
              onClick={() => setSeverityFilter('routine')}
              className={`px-2.5 py-1 rounded-md transition ${severityFilter === 'routine' ? 'bg-[var(--severity-routine-bg)] text-[var(--severity-routine-color)] font-semibold' : 'text-[var(--text-secondary)]'}`}
            >
              Routine
            </button>
          </div>
        </div>
      </div>

      {/* Dense Data Table */}
      <div className="card-panel p-0 overflow-hidden border-[var(--border-subtle)]">
        <table className="data-table">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Ward</th>
              <th>Patient ID</th>
              <th>Clinical Event Type</th>
              <th>Expected Time</th>
              <th>Actual Time</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredGaps.map((gap) => (
              <tr key={gap.gap_id} onClick={() => handleRowClick(gap)}>
                <td>
                  <span className={`badge-severity ${
                    gap.severity === 'urgent' ? 'badge-urgent' : gap.severity === 'routine' ? 'badge-routine' : 'badge-doc'
                  }`}>
                    {gap.severity === 'urgent' && <AlertTriangle className="w-3 h-3" />}
                    {gap.severity === 'routine' && <Clock className="w-3 h-3" />}
                    {gap.severity === 'doc' && <Info className="w-3 h-3" />}
                    <span className="capitalize">{gap.severity}</span>
                  </span>
                </td>
                <td className="font-mono text-xs">{gap.ward_id}</td>
                <td className="font-mono text-xs font-semibold">{gap.patient_id}</td>
                <td className="capitalize text-xs">{gap.event_type.replace('_', ' ')}</td>
                <td className="font-mono text-xs">{new Date(gap.expected_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                <td className="font-mono text-xs">{gap.actual_time !== '—' ? new Date(gap.actual_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                <td>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-mono uppercase font-semibold ${
                    gap.status === 'open' ? 'bg-[var(--severity-urgent-bg)] text-[var(--severity-urgent-color)]' : 'bg-[var(--severity-resolved-bg)] text-[var(--severity-resolved-color)]'
                  }`}>
                    {gap.status}
                  </span>
                </td>
                <td>
                  <ChevronRight className="w-4 h-4 text-[var(--text-muted)]" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Gap Detail Slide-In Drawer */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title={selectedGap ? `GAP DETAIL · ${selectedGap.gap_id}` : 'GAP DETAIL'}
      >
        {selectedGap && (
          <div className="space-y-5 text-xs">
            {/* Severity Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
              <span className={`badge-severity ${
                selectedGap.severity === 'urgent' ? 'badge-urgent' : selectedGap.severity === 'routine' ? 'badge-routine' : 'badge-doc'
              }`}>
                {selectedGap.severity === 'urgent' && <AlertTriangle className="w-3.5 h-3.5" />}
                {selectedGap.severity === 'routine' && <Clock className="w-3.5 h-3.5" />}
                {selectedGap.severity === 'doc' && <Info className="w-3.5 h-3.5" />}
                <span className="capitalize">{selectedGap.severity} Severity</span>
              </span>

              <span className="font-mono text-[var(--text-muted)]">Status: {selectedGap.status.toUpperCase()}</span>
            </div>

            {/* Gap Description (LLM-authored) */}
            <div className="space-y-1">
              <div className="flex justify-between items-center">
                <label className="label-ui">Gap Summary & Description</label>
                {selectedGap.model_version && (
                  <span className="text-[9px] font-mono bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded flex items-center gap-1">
                    ✨ AI-Generated ({selectedGap.model_version})
                  </span>
                )}
              </div>
              <p className="p-3 bg-[var(--canvas-bg)] border border-[var(--border-subtle)] rounded-lg text-[var(--text-primary)] font-medium">
                {selectedGap.description}
              </p>
            </div>

            {/* Event Metadata grid */}
            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="p-2.5 bg-[var(--canvas-bg)] rounded-md border border-[var(--border-subtle)]">
                <span className="text-[10px] text-[var(--text-muted)] block uppercase">Patient ID</span>
                <span className="font-bold text-[var(--text-primary)]">{selectedGap.patient_id}</span>
              </div>
              <div className="p-2.5 bg-[var(--canvas-bg)] rounded-md border border-[var(--border-subtle)]">
                <span className="text-[10px] text-[var(--text-muted)] block uppercase">Ward ID</span>
                <span className="font-bold text-[var(--text-primary)]">{selectedGap.ward_id}</span>
              </div>
              <div className="p-2.5 bg-[var(--canvas-bg)] rounded-md border border-[var(--border-subtle)]">
                <span className="text-[10px] text-[var(--text-muted)] block uppercase">Expected Time</span>
                <span className="text-[var(--text-primary)]">{new Date(selectedGap.expected_time).toLocaleString()}</span>
              </div>
              <div className="p-2.5 bg-[var(--canvas-bg)] rounded-md border border-[var(--border-subtle)]">
                <span className="text-[10px] text-[var(--text-muted)] block uppercase">Assigned Staff</span>
                <span className="text-[var(--text-primary)]">{selectedGap.assigned_to}</span>
              </div>
            </div>

            {/* Raw Clinical Note */}
            <div className="space-y-1">
              <label className="label-ui">Raw Clinical Staff Note</label>
              <p className="p-3 bg-[var(--canvas-bg)] border border-[var(--border-subtle)] rounded-lg text-[var(--text-secondary)] italic">
                "{selectedGap.raw_note}"
              </p>
            </div>

            {/* Acknowledge Action button */}
            {selectedGap.status === 'open' && (
              <div className="pt-4 border-t border-[var(--border-subtle)] space-y-2">
                <button
                  onClick={() => {
                    alert(`Acknowledged gap ${selectedGap.gap_id}`);
                    setIsDrawerOpen(false);
                  }}
                  className={`btn-ui w-full py-2.5 ${selectedGap.severity === 'urgent' ? 'btn-ui-urgent' : 'btn-ui-primary'}`}
                >
                  <Check className="w-4 h-4" />
                  <span>Acknowledge Gap ({selectedGap.severity.toUpperCase()})</span>
                </button>
                {selectedGap.severity === 'urgent' && (
                  <p className="text-[10px] text-[var(--text-muted)] text-center font-mono">
                    Urgent gaps require mandatory individual confirmation.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
