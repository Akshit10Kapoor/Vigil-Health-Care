import React, { useState } from 'react';
import { Pill, CheckCircle2, ShieldCheck, Eye, UserCheck } from 'lucide-react';
import TypeaheadCombobox from '../components/TypeaheadCombobox';
import { queueEvent } from '../services/local_db';

export default function MedOrderLog({ patients = [], wards = [], staff, onEventQueued }) {
  const [selectedPatientId, setSelectedPatientId] = useState(patients[0]?.patient_id || 'PAT_1001');
  const [medicationName, setMedicationName] = useState('Inj. Piperacillin-Tazobactam 4.5g');
  const [dosage, setDosage] = useState('4.5g IV in 100ml NS');
  const [route, setRoute] = useState('IV Infusion');
  const [isHighAlert, setIsHighAlert] = useState(false);
  const [verifyingNurseId, setVerifyingNurseId] = useState('NURSE_102');
  const [successMsg, setSuccessMsg] = useState('');

  const selectedPatient = patients.find(p => p.patient_id === selectedPatientId) || patients[0] || {
    patient_id: 'PAT_1001', full_name: 'Ramesh Verma', bed_number: 'Bed-01', ward_id: 'ICU_01'
  };

  const patientOptions = patients.map(p => ({
    value: p.patient_id,
    label: `${p.full_name} (${p.patient_id})`,
    sublabel: `Bed ${p.bed_number} · ${p.ward_id}`
  }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSuccessMsg('');

    const eventPayload = {
      event_type: 'medication_order_documentation',
      patient_id: selectedPatient.patient_id,
      ward_id: selectedPatient.ward_id,
      bed_number: selectedPatient.bed_number,
      staff_id: staff?.staff_id || 'NURSE_101',
      device_timestamp: new Date().toISOString(),
      device_tz_offset: '+05:30',
      payload: {
        medication_name: medicationName,
        dosage: dosage,
        route: route,
        administered_at: new Date().toISOString(),
        is_high_alert_med: isHighAlert,
        verifying_nurse_id: verifyingNurseId || null,
        two_nurse_verification_performed: isHighAlert || !!verifyingNurseId
      },
      metadata: {
        nabh_chapter_ref: 'MOM_6'
      }
    };

    const record = await queueEvent(eventPayload);
    setSuccessMsg(`Medication Order for ${medicationName} logged! (Queued offline)`);

    if (onEventQueued) {
      onEventQueued(record);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
          <Pill className="w-4 h-4 text-[var(--accent-teal)]" />
          <span>Medication Administration Documentation</span>
        </h2>
        <p className="text-xs text-[var(--text-secondary)]">NABH MOM Standards — Administration log & dual-nurse verification</p>
      </div>

      {successMsg && (
        <div className="p-3 bg-[var(--severity-resolved-bg)] border border-[var(--severity-resolved-border)] text-[var(--severity-resolved-color)] rounded-lg flex items-center gap-3 text-xs font-semibold">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* 2-Column Laptop Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Form Left (3 cols) */}
        <form onSubmit={handleSubmit} className="lg:col-span-3 space-y-5">
          <div className="card-panel space-y-2">
            <label className="label-ui">Select Patient (Typeahead Search)</label>
            <TypeaheadCombobox
              options={patientOptions}
              selectedValue={selectedPatientId}
              onSelect={setSelectedPatientId}
              placeholder="Type patient name or ID..."
            />
          </div>

          <div className="card-panel space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="sm:col-span-2">
                <label className="label-ui">Medication Brand / Generic Name</label>
                <input
                  type="text"
                  required
                  value={medicationName}
                  onChange={(e) => setMedicationName(e.target.value)}
                  className="input-ui text-xs font-medium"
                  placeholder="e.g. Inj. Piperacillin-Tazobactam 4.5g"
                />
              </div>

              <div>
                <label className="label-ui">Route</label>
                <select
                  value={route}
                  onChange={(e) => setRoute(e.target.value)}
                  className="input-ui text-xs"
                >
                  <option value="IV Infusion">IV Infusion</option>
                  <option value="IV Push">IV Push</option>
                  <option value="Oral">Oral (PO)</option>
                  <option value="Subcutaneous">Subcutaneous (SC)</option>
                  <option value="Intramuscular">Intramuscular (IM)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="label-ui">Dosage & Infusion Instructions</label>
              <input
                type="text"
                required
                value={dosage}
                onChange={(e) => setDosage(e.target.value)}
                className="input-ui text-xs"
                placeholder="e.g. 4.5g IV in 100ml NS over 30 mins"
              />
            </div>
          </div>

          {/* High Alert & Dual Nurse Verification */}
          <div className="card-panel space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--accent-teal)] font-mono flex items-center gap-1.5">
              <UserCheck className="w-4 h-4" />
              <span>Dual Nurse Verification</span>
            </h3>

            <label className="flex items-center gap-3 p-2.5 bg-[var(--canvas-bg)] rounded-lg cursor-pointer border border-[var(--border-subtle)] text-xs">
              <input
                type="checkbox"
                checked={isHighAlert}
                onChange={(e) => setIsHighAlert(e.target.checked)}
                className="w-4 h-4 accent-teal-600 rounded"
              />
              <div>
                <span className="font-semibold text-[var(--text-primary)]">High-Alert Medication (HAM)</span>
                <p className="text-[10px] text-[var(--text-muted)]">Mandatory independent secondary verification required</p>
              </div>
            </label>

            <div>
              <label className="label-ui">Secondary Verifying Nurse Staff ID</label>
              <input
                type="text"
                value={verifyingNurseId}
                onChange={(e) => setVerifyingNurseId(e.target.value)}
                className="input-ui text-xs font-mono"
                placeholder="e.g. NURSE_102"
              />
            </div>
          </div>

          <button type="submit" className="btn-ui btn-ui-primary w-full py-3 text-sm font-semibold sticky bottom-4 shadow-lg">
            <Pill className="w-4 h-4" />
            <span>Log Medication Administration</span>
          </button>
        </form>

        {/* Live Preview Panel Right (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-1.5">
              <Eye className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Live Event Store Preview</span>
            </h3>
            <span className="text-[10px] font-mono text-[var(--text-muted)]">Canonical Record</span>
          </div>

          <div className="card-panel space-y-3 font-mono text-xs border-[var(--accent-teal)] border-opacity-30 bg-[var(--canvas-bg)]">
            <div className="flex items-center justify-between pb-2 border-b border-[var(--border-subtle)] text-[10px]">
              <span className="text-[var(--accent-teal)] font-bold">TYPE: MEDICATION_DOCUMENTATION</span>
              <span className="text-[var(--text-muted)]">NABH MOM_6</span>
            </div>

            <div>
              <p className="text-[10px] text-[var(--text-muted)] uppercase">Target Patient</p>
              <p className="font-bold text-[var(--text-primary)]">{selectedPatient.full_name} ({selectedPatient.patient_id})</p>
              <p className="text-[11px] text-[var(--text-secondary)]">Bed: {selectedPatient.bed_number} · Ward: {selectedPatient.ward_id}</p>
            </div>

            <div className="p-2.5 bg-[var(--card-bg)] border border-[var(--border-subtle)] rounded-md space-y-1">
              <p className="text-[10px] text-[var(--text-muted)] uppercase">Medication Details</p>
              <p className="text-[var(--text-primary)]">{medicationName} ({route})</p>
              <p className="text-[var(--text-secondary)]">Dosage: {dosage}</p>
              <p className="text-[var(--text-secondary)]">High-Alert Med: {isHighAlert ? 'YES' : 'NO'}</p>
              <p className="text-[var(--text-secondary)]">Verifying Nurse: {verifyingNurseId || 'None'}</p>
            </div>

            <div className="pt-2 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)] flex items-center justify-between">
              <span>Admin Nurse: {staff?.staff_id || 'NURSE_101'}</span>
              <span>Timezone: +05:30</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
