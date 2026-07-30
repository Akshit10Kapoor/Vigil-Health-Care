import React, { useState } from 'react';
import { ClipboardList, CheckCircle2, HeartPulse, Activity, Eye, ShieldCheck } from 'lucide-react';
import TypeaheadCombobox from '../components/TypeaheadCombobox';
import { queueEvent } from '../services/local_db';

export default function RoundChecklist({ patients = [], wards = [], staff, onEventQueued }) {
  const [selectedPatientId, setSelectedPatientId] = useState(patients[0]?.patient_id || 'PAT_1001');
  const [sysBP, setSysBP] = useState('120');
  const [diaBP, setDiaBP] = useState('80');
  const [pulse, setPulse] = useState('76');
  const [spo2, setSpo2] = useState('98');
  const [temp, setTemp] = useState('98.6');
  const [painScore, setPainScore] = useState('0');
  const [positionChange, setPositionChange] = useState('Left lateral');
  const [ivSiteCheck, setIvSiteCheck] = useState('Clean & Intact');
  const [rawNote, setRawNote] = useState('');
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
      event_type: 'nursing_round',
      patient_id: selectedPatient.patient_id,
      ward_id: selectedPatient.ward_id,
      bed_number: selectedPatient.bed_number,
      staff_id: staff?.staff_id || 'NURSE_101',
      device_timestamp: new Date().toISOString(),
      device_tz_offset: '+05:30',
      payload: {
        vitals: {
          bp: `${sysBP}/${diaBP}`,
          pulse: parseInt(pulse, 10),
          spo2: parseInt(spo2, 10),
          temp_f: parseFloat(temp),
          pain_score: parseInt(painScore, 10)
        },
        position_change: positionChange,
        iv_site_check: ivSiteCheck
      },
      raw_note: rawNote || null,
      metadata: {
        app_version: '1.0.0-phase1-laptop',
        device: 'Ward Station Desktop'
      }
    };

    const record = await queueEvent(eventPayload);
    setSuccessMsg(`Nursing Round logged for ${selectedPatient.full_name}! (Queued offline)`);
    setRawNote('');

    if (onEventQueued) {
      onEventQueued(record);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-[var(--accent-teal)]" />
          <span>Nursing Round Verification Checklist</span>
        </h2>
        <p className="text-xs text-[var(--text-secondary)]">Log time-bound vitals and patient monitoring checks</p>
      </div>

      {successMsg && (
        <div className="p-3 bg-[var(--severity-resolved-bg)] border border-[var(--severity-resolved-border)] text-[var(--severity-resolved-color)] rounded-lg flex items-center gap-3 text-xs font-semibold">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* 2-Column Laptop Layout: Form Left (60%), Live Preview Right (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Form Column (3 cols) */}
        <form onSubmit={handleSubmit} className="lg:col-span-3 space-y-5">
          {/* Patient Selection Typeahead */}
          <div className="card-panel space-y-2">
            <label className="label-ui">Select Patient (Typeahead Search)</label>
            <TypeaheadCombobox
              options={patientOptions}
              selectedValue={selectedPatientId}
              onSelect={setSelectedPatientId}
              placeholder="Type patient name or ID..."
            />
          </div>

          {/* Vitals Grid */}
          <div className="card-panel space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--accent-teal)] flex items-center gap-2 font-mono">
              <HeartPulse className="w-4 h-4" />
              <span>Vital Signs Capture</span>
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="label-ui">BP (Sys/Dia)</label>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    value={sysBP}
                    onChange={(e) => setSysBP(e.target.value)}
                    className="input-ui font-mono text-center font-bold text-sm px-1"
                    placeholder="120"
                    required
                  />
                  <span className="font-bold text-[var(--text-muted)]">/</span>
                  <input
                    type="number"
                    value={diaBP}
                    onChange={(e) => setDiaBP(e.target.value)}
                    className="input-ui font-mono text-center font-bold text-sm px-1"
                    placeholder="80"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="label-ui">Pulse (bpm)</label>
                <input
                  type="number"
                  value={pulse}
                  onChange={(e) => setPulse(e.target.value)}
                  className="input-ui font-mono text-center font-bold text-sm"
                  placeholder="76"
                  required
                />
              </div>

              <div>
                <label className="label-ui">SpO2 (%)</label>
                <input
                  type="number"
                  value={spo2}
                  onChange={(e) => setSpo2(e.target.value)}
                  className="input-ui font-mono text-center font-bold text-sm"
                  placeholder="98"
                  required
                />
              </div>

              <div>
                <label className="label-ui">Pain (0–10)</label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={painScore}
                  onChange={(e) => setPainScore(e.target.value)}
                  className="input-ui font-mono text-center font-bold text-sm"
                  placeholder="0"
                  required
                />
              </div>
            </div>
          </div>

          {/* Nursing Interventions */}
          <div className="card-panel space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--accent-teal)] flex items-center gap-2 font-mono">
              <Activity className="w-4 h-4" />
              <span>Nursing Interventions</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label-ui">Position Change</label>
                <select
                  value={positionChange}
                  onChange={(e) => setPositionChange(e.target.value)}
                  className="input-ui text-xs"
                >
                  <option value="Left lateral">Left Lateral</option>
                  <option value="Right lateral">Right Lateral</option>
                  <option value="Supine">Supine (Flat)</option>
                  <option value="High Fowlers">High Fowler's</option>
                  <option value="Ambulatory / Out of bed">Ambulatory</option>
                </select>
              </div>

              <div>
                <label className="label-ui">IV Site Status</label>
                <select
                  value={ivSiteCheck}
                  onChange={(e) => setIvSiteCheck(e.target.value)}
                  className="input-ui text-xs"
                >
                  <option value="Clean & Intact">Clean & Intact</option>
                  <option value="Redness / Slight Pain">Redness / Slight Pain</option>
                  <option value="Swollen / Infiltrated">Swollen / Infiltrated</option>
                  <option value="N/A (No IV)">N/A (No IV line)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="label-ui">Raw Clinical Staff Note</label>
              <textarea
                value={rawNote}
                onChange={(e) => setRawNote(e.target.value)}
                rows={2}
                className="input-ui text-xs"
                placeholder="e.g. Patient resting comfortably. Patient refused vitals initially, retried 15 min later."
              ></textarea>
            </div>
          </div>

          <button type="submit" className="btn-ui btn-ui-primary w-full py-3 text-sm font-semibold sticky bottom-4 shadow-lg">
            <ClipboardList className="w-4 h-4" />
            <span>Save & Log Nursing Round</span>
          </button>
        </form>

        {/* Live Event Preview Panel Right (2 cols) */}
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
              <span className="text-[var(--accent-teal)] font-bold">TYPE: NURSING_ROUND</span>
              <span className="text-[var(--text-muted)]">OFFLINE QUEUE</span>
            </div>

            <div className="space-y-1">
              <p className="text-[10px] text-[var(--text-muted)] uppercase">Target Patient</p>
              <p className="font-bold text-[var(--text-primary)]">{selectedPatient.full_name} ({selectedPatient.patient_id})</p>
              <p className="text-[11px] text-[var(--text-secondary)]">Bed: {selectedPatient.bed_number} · Ward: {selectedPatient.ward_id}</p>
            </div>

            <div className="p-2.5 bg-[var(--card-bg)] border border-[var(--border-subtle)] rounded-md space-y-1">
              <p className="text-[10px] text-[var(--text-muted)] uppercase">Extracted Payload</p>
              <p className="text-[var(--text-primary)]">Vitals: BP {sysBP}/{diaBP} mmHg · Pulse {pulse} bpm · SpO2 {spo2}% · Pain {painScore}/10</p>
              <p className="text-[var(--text-secondary)]">Position: {positionChange} · IV Site: {ivSiteCheck}</p>
            </div>

            {rawNote && (
              <div className="space-y-1">
                <p className="text-[10px] text-[var(--text-muted)] uppercase">Raw Note Transcript</p>
                <p className="italic text-[var(--text-secondary)]">"{rawNote}"</p>
              </div>
            )}

            <div className="pt-2 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)] flex items-center justify-between">
              <span>Staff: {staff?.staff_id || 'NURSE_101'}</span>
              <span>Timezone: +05:30</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
