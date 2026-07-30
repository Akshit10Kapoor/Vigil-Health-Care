import React, { useState, useRef } from 'react';
import { FileCheck, CheckCircle2, Eraser, Eye, ShieldAlert } from 'lucide-react';
import TypeaheadCombobox from '../components/TypeaheadCombobox';
import { queueEvent } from '../services/local_db';

export default function ConsentCapture({ patients = [], wards = [], staff, onEventQueued }) {
  const [selectedPatientId, setSelectedPatientId] = useState(patients[0]?.patient_id || 'PAT_1001');
  const [procedureName, setProcedureName] = useState('Central Line Insertion');
  const [doctorName, setDoctorName] = useState('Dr. Aris Thorne');
  const [risksExplained, setRisksExplained] = useState(true);
  const [alternativesDiscussed, setAlternativesDiscussed] = useState(true);
  const [witnessName, setWitnessName] = useState('Nurse Priya Patel');
  const [successMsg, setSuccessMsg] = useState('');

  const canvasRef = useRef(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);

  const selectedPatient = patients.find(p => p.patient_id === selectedPatientId) || patients[0] || {
    patient_id: 'PAT_1001', full_name: 'Ramesh Verma', bed_number: 'Bed-01', ward_id: 'ICU_01'
  };

  const patientOptions = patients.map(p => ({
    value: p.patient_id,
    label: `${p.full_name} (${p.patient_id})`,
    sublabel: `Bed ${p.bed_number} · ${p.ward_id}`
  }));

  const startDrawing = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || (e.touches && e.touches[0].clientX)) - rect.left;
    const y = (e.clientY || (e.touches && e.touches[0].clientY)) - rect.top;
    
    ctx.beginPath();
    ctx.moveTo(x, y);
    setIsDrawing(true);
    setHasSignature(true);
  };

  const draw = (e) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || (e.touches && e.touches[0].clientX)) - rect.left;
    const y = (e.clientY || (e.touches && e.touches[0].clientY)) - rect.top;

    ctx.strokeStyle = '#0d9488';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const stopDrawing = () => setIsDrawing(false);

  const clearSignature = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSuccessMsg('');

    let signatureBase64 = null;
    if (hasSignature && canvasRef.current) {
      signatureBase64 = canvasRef.current.toDataURL('image/png');
    }

    const eventPayload = {
      event_type: 'consent_capture',
      patient_id: selectedPatient.patient_id,
      ward_id: selectedPatient.ward_id,
      bed_number: selectedPatient.bed_number,
      staff_id: staff?.staff_id || 'NURSE_101',
      device_timestamp: new Date().toISOString(),
      device_tz_offset: '+05:30',
      payload: {
        procedure_name: procedureName,
        doctor_name: doctorName,
        risks_explained: risksExplained,
        alternatives_discussed: alternativesDiscussed,
        witness_name: witnessName,
        signature_base64: signatureBase64
      },
      metadata: {
        nabh_chapter_ref: 'COP_3',
        signature_captured: !!signatureBase64
      }
    };

    const record = await queueEvent(eventPayload);
    setSuccessMsg(`Informed Consent for ${procedureName} captured! (Queued offline)`);
    clearSignature();

    if (onEventQueued) {
      onEventQueued(record);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
          <FileCheck className="w-4 h-4 text-[var(--accent-teal)]" />
          <span>Informed Consent Verification</span>
        </h2>
        <p className="text-xs text-[var(--text-secondary)]">NABH COP Chapter — Pre-procedure consent capture & digital signature</p>
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="label-ui">Procedure / High-Risk Action</label>
                <input
                  type="text"
                  required
                  value={procedureName}
                  onChange={(e) => setProcedureName(e.target.value)}
                  className="input-ui text-xs"
                  placeholder="e.g. Central Line Insertion"
                />
              </div>

              <div>
                <label className="label-ui">Attending Doctor</label>
                <input
                  type="text"
                  required
                  value={doctorName}
                  onChange={(e) => setDoctorName(e.target.value)}
                  className="input-ui text-xs"
                  placeholder="e.g. Dr. Aris Thorne"
                />
              </div>
            </div>
          </div>

          {/* Verification Checklist */}
          <div className="card-panel space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--accent-teal)] font-mono">NABH Checklist</h3>
            
            <label className="flex items-center gap-3 p-2.5 bg-[var(--canvas-bg)] rounded-lg cursor-pointer border border-[var(--border-subtle)] text-xs">
              <input
                type="checkbox"
                checked={risksExplained}
                onChange={(e) => setRisksExplained(e.target.checked)}
                className="w-4 h-4 accent-teal-600 rounded"
              />
              <span>Risks, complications, and side effects explained to patient/family</span>
            </label>

            <label className="flex items-center gap-3 p-2.5 bg-[var(--canvas-bg)] rounded-lg cursor-pointer border border-[var(--border-subtle)] text-xs">
              <input
                type="checkbox"
                checked={alternativesDiscussed}
                onChange={(e) => setAlternativesDiscussed(e.target.checked)}
                className="w-4 h-4 accent-teal-600 rounded"
              />
              <span>Alternative treatment options discussed</span>
            </label>

            <div>
              <label className="label-ui">Witness Name & Staff Role</label>
              <input
                type="text"
                value={witnessName}
                onChange={(e) => setWitnessName(e.target.value)}
                className="input-ui text-xs"
                placeholder="e.g. Nurse Priya Patel (Staff Nurse)"
              />
            </div>
          </div>

          {/* Digital Signature Canvas */}
          <div className="card-panel space-y-2">
            <div className="flex items-center justify-between">
              <label className="label-ui">Digital Signature Pad</label>
              <button type="button" onClick={clearSignature} className="text-xs text-rose-500 flex items-center gap-1 font-medium">
                <Eraser className="w-3.5 h-3.5" /> Clear
              </button>
            </div>
            <div className="signature-canvas p-1 flex justify-center">
              <canvas
                ref={canvasRef}
                width={450}
                height={120}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                className="w-full max-w-[450px] h-[120px] bg-[var(--card-bg)] rounded border border-[var(--border-subtle)]"
              />
            </div>
          </div>

          <button type="submit" className="btn-ui btn-ui-primary w-full py-3 text-sm font-semibold sticky bottom-4 shadow-lg">
            <FileCheck className="w-4 h-4" />
            <span>Capture & Verify Consent</span>
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
              <span className="text-[var(--accent-teal)] font-bold">TYPE: CONSENT_CAPTURE</span>
              <span className="text-[var(--text-muted)]">NABH COP_3</span>
            </div>

            <div>
              <p className="text-[10px] text-[var(--text-muted)] uppercase">Patient & Procedure</p>
              <p className="font-bold text-[var(--text-primary)]">{selectedPatient.full_name} ({selectedPatient.patient_id})</p>
              <p className="text-[11px] text-[var(--text-secondary)]">{procedureName} · Dr. {doctorName}</p>
            </div>

            <div className="p-2.5 bg-[var(--card-bg)] border border-[var(--border-subtle)] rounded-md space-y-1">
              <p className="text-[10px] text-[var(--text-muted)] uppercase">Checklist Validation</p>
              <p className="text-[var(--text-primary)]">Risks Explained: {risksExplained ? 'YES' : 'NO'}</p>
              <p className="text-[var(--text-primary)]">Alternatives: {alternativesDiscussed ? 'YES' : 'NO'}</p>
              <p className="text-[var(--text-secondary)]">Witness: {witnessName}</p>
              <p className="text-[var(--text-secondary)]">Signature Attached: {hasSignature ? 'YES (File Ref)' : 'NO'}</p>
            </div>

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
