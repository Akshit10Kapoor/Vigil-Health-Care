import React, { useState } from 'react';
import { Users, Search, ChevronRight, Activity, Clock, ShieldCheck } from 'lucide-react';
import Drawer from '../components/Drawer';

export default function PatientRegistry({ patients = [], queuedEvents = [] }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const filteredPatients = patients.filter(p =>
    p.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.patient_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.bed_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.ward_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleRowClick = (patient) => {
    setSelectedPatient(patient);
    setIsDrawerOpen(true);
  };

  // Filter events for selected patient
  const patientEvents = selectedPatient
    ? queuedEvents.filter(e => e.patient_id === selectedPatient.patient_id)
    : [];

  return (
    <div className="space-y-4">
      {/* Search Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
            <Users className="w-4 h-4 text-[var(--accent-teal)]" />
            <span>Admitted Patient Registry</span>
          </h2>
          <p className="text-xs text-[var(--text-secondary)] font-mono">Patient directory & individual verification timelines</p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search patient name, ID, or bed..."
            className="input-ui pl-9 text-xs"
          />
        </div>
      </div>

      {/* Patient Table */}
      <div className="card-panel p-0 overflow-hidden border-[var(--border-subtle)]">
        <table className="data-table">
          <thead>
            <tr>
              <th>Patient ID</th>
              <th>Full Name</th>
              <th>Bed Number</th>
              <th>Ward ID</th>
              <th>Age / Gender</th>
              <th>Acuity</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredPatients.map((patient) => (
              <tr key={patient.patient_id} onClick={() => handleRowClick(patient)}>
                <td className="font-mono text-xs font-semibold">{patient.patient_id}</td>
                <td className="font-semibold text-xs text-[var(--text-primary)]">{patient.full_name}</td>
                <td className="font-mono text-xs">{patient.bed_number}</td>
                <td className="font-mono text-xs">{patient.ward_id}</td>
                <td className="text-xs">{patient.age} / {patient.gender}</td>
                <td>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[var(--canvas-bg)] border border-[var(--border-subtle)] font-medium">
                    {patient.acuity_level}
                  </span>
                </td>
                <td>
                  <span className="badge-severity badge-resolved">
                    <ShieldCheck className="w-3 h-3" />
                    <span>Admitted</span>
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

      {/* Patient Timeline Detail Drawer */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title={selectedPatient ? `PATIENT AUDIT TIMELINE · ${selectedPatient.patient_id}` : 'PATIENT TIMELINE'}
      >
        {selectedPatient && (
          <div className="space-y-5 text-xs">
            {/* Summary */}
            <div className="p-3 bg-[var(--canvas-bg)] border border-[var(--border-subtle)] rounded-lg space-y-1">
              <h4 className="font-bold text-sm text-[var(--text-primary)]">{selectedPatient.full_name}</h4>
              <p className="font-mono text-[var(--text-secondary)]">
                Bed: {selectedPatient.bed_number} · Ward: {selectedPatient.ward_id} · Acuity: {selectedPatient.acuity_level.toUpperCase()}
              </p>
            </div>

            {/* Chronological Audit Timeline */}
            <div className="space-y-3">
              <h4 className="label-ui flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-[var(--accent-teal)]" />
                <span>Chronological Event History Log</span>
              </h4>

              {patientEvents.length === 0 ? (
                <div className="p-6 text-center text-[var(--text-muted)] font-mono border border-dashed border-[var(--border-medium)] rounded-lg">
                  No clinical events logged for patient {selectedPatient.patient_id} yet.
                </div>
              ) : (
                <div className="relative pl-4 space-y-4 border-l-2 border-[var(--border-medium)]">
                  {patientEvents.map((evt, idx) => (
                    <div key={evt.client_sync_id || idx} className="relative space-y-1">
                      <div className="absolute -left-[21px] top-1 w-3 h-3 rounded-full bg-[var(--accent-teal)] border-2 border-[var(--card-bg)]" />
                      <div className="flex items-center justify-between font-mono text-[10px] text-[var(--text-muted)]">
                        <span>{new Date(evt.device_timestamp).toLocaleString()}</span>
                        <span className="uppercase text-[var(--accent-teal)]">{evt.event_type.replace('_', ' ')}</span>
                      </div>
                      <div className="p-2.5 bg-[var(--canvas-bg)] border border-[var(--border-subtle)] rounded-md font-mono text-xs">
                        <p className="font-semibold text-[var(--text-primary)] capitalize">{evt.event_type.replace('_', ' ')}</p>
                        {evt.raw_note && <p className="text-[var(--text-secondary)] italic mt-1">"{evt.raw_note}"</p>}
                        <p className="text-[10px] text-[var(--text-muted)] mt-1">Logged by: {evt.staff_id}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
