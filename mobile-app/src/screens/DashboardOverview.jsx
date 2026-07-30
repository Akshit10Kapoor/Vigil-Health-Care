import React from 'react';
import { Shield, AlertTriangle, Clock, CheckCircle2, Info, ArrowUpRight, Activity } from 'lucide-react';

export default function DashboardOverview({ wards, queuedEvents, onSelectWard, onOpenGapDetail }) {
  // Compute KPI metrics
  const totalEvents = queuedEvents.length;
  const openUrgentGaps = 1; // Demo urgent gap
  const openRoutineGaps = 2;
  const coverageRate = 96;
  const onTimeRate = 94;

  // Mock live activity feed stream
  const activityStream = [
    {
      id: 'act_101',
      severity: 'urgent',
      ward_id: 'ICU_01',
      patient_id: 'PAT_1001',
      title: 'Missed 2-Hour ICU Vitals Verification',
      description: 'ICU Patient PAT_1001 vitals check overdue by 35 minutes. Expectation rule requires vitals every 120 min for high acuity.',
      timestamp: new Date(Date.now() - 35 * 60000).toISOString()
    },
    {
      id: 'act_102',
      severity: 'routine',
      ward_id: 'SURG_3A',
      patient_id: 'PAT_2001',
      title: 'Post-Op Consent Signature Documentation',
      description: 'Central Line consent form logged with witness signature attached.',
      timestamp: new Date(Date.now() - 65 * 60000).toISOString()
    },
    {
      id: 'act_103',
      severity: 'doc',
      ward_id: 'ICU_01',
      patient_id: 'PAT_1002',
      title: 'High-Alert Insulin Administration',
      description: 'Dual-nurse verification logged by NURSE_101 and NURSE_102.',
      timestamp: new Date(Date.now() - 110 * 60000).toISOString()
    }
  ];

  return (
    <div className="space-y-6">
      {/* KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-panel border-l-4 border-l-[var(--severity-urgent-color)]">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider">Open Urgent Gaps</span>
            <AlertTriangle className="w-4 h-4 text-[var(--severity-urgent-color)]" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[var(--severity-urgent-color)]">{openUrgentGaps}</span>
            <span className="text-xs text-[var(--text-muted)] font-mono">Immediate Action</span>
          </div>
        </div>

        <div className="card-panel border-l-4 border-l-[var(--accent-teal)]">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider">Ward Protocol Coverage</span>
            <Shield className="w-4 h-4 text-[var(--accent-teal)]" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[var(--text-primary)]">{coverageRate}%</span>
            <span className="text-xs text-[var(--severity-resolved-color)] font-mono flex items-center">
              +2.1% <ArrowUpRight className="w-3 h-3" />
            </span>
          </div>
        </div>

        <div className="card-panel border-l-4 border-l-[var(--severity-routine-color)]">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider">Routine Pending Gaps</span>
            <Clock className="w-4 h-4 text-[var(--severity-routine-color)]" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[var(--severity-routine-color)]">{openRoutineGaps}</span>
            <span className="text-xs text-[var(--text-muted)] font-mono">Shift Review</span>
          </div>
        </div>

        <div className="card-panel border-l-4 border-l-[var(--severity-resolved-color)]">
          <div className="flex items-center justify-between text-[var(--text-secondary)]">
            <span className="text-xs font-semibold uppercase tracking-wider">Protocol On-Time Rate</span>
            <CheckCircle2 className="w-4 h-4 text-[var(--severity-resolved-color)]" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[var(--text-primary)]">{onTimeRate}%</span>
            <span className="text-xs text-[var(--severity-resolved-color)] font-mono">NABH Compliant</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Ward List (65%) + Live Activity Stream (35%) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ward Overview List (Left 2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
              <Shield className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Ward Compliance Overview</span>
            </h3>
            <span className="text-xs font-mono text-[var(--text-muted)]">{wards.length} Active Wards</span>
          </div>

          <div className="space-y-3">
            {wards.map((ward) => {
              const isICU = ward.ward_id === 'ICU_01';
              return (
                <div
                  key={ward.ward_id}
                  onClick={() => onSelectWard(ward.ward_id)}
                  className="card-panel hover:border-[var(--accent-teal)] cursor-pointer flex items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-sm text-[var(--text-primary)]">{ward.name}</h4>
                      <span className="text-[10px] font-mono font-semibold uppercase px-2 py-0.5 rounded bg-[var(--canvas-bg)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                        {ward.acuity_level} Acuity
                      </span>
                    </div>
                    <p className="text-xs font-mono text-[var(--text-muted)]">
                      Ward ID: {ward.ward_id} · Capacity: {ward.capacity} Beds
                    </p>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Severity counters */}
                    <div className="flex items-center gap-3 text-xs font-mono">
                      <div className="flex items-center gap-1" title="Urgent Gaps">
                        <span className="w-2.5 h-2.5 rounded-full bg-[var(--severity-urgent-color)]" />
                        <span className="font-bold">{isICU ? 1 : 0}</span>
                      </div>
                      <div className="flex items-center gap-1" title="Routine Gaps">
                        <span className="w-2.5 h-2.5 rounded-full bg-[var(--severity-routine-color)]" />
                        <span className="font-bold">{isICU ? 1 : 1}</span>
                      </div>
                    </div>

                    <div className="text-right font-mono text-xs text-[var(--text-muted)] hidden sm:block">
                      <p className="text-[10px] uppercase">Last Verified</p>
                      <p className="text-[var(--text-secondary)]">12 mins ago</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live Activity Stream (Right col) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-[var(--text-primary)] font-mono uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--accent-teal)]" />
              <span>Live Verification Stream</span>
            </h3>
            <span className="text-xs font-mono text-[var(--text-muted)]">Real-time</span>
          </div>

          <div className="space-y-3">
            {activityStream.map((act) => (
              <div
                key={act.id}
                onClick={() => onOpenGapDetail(act)}
                className="card-panel hover:bg-[var(--card-hover)] cursor-pointer space-y-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className={`badge-severity ${
                    act.severity === 'urgent' ? 'badge-urgent' : act.severity === 'routine' ? 'badge-routine' : 'badge-doc'
                  }`}>
                    {act.severity === 'urgent' && <AlertTriangle className="w-3 h-3" />}
                    {act.severity === 'routine' && <Clock className="w-3 h-3" />}
                    {act.severity === 'doc' && <Info className="w-3 h-3" />}
                    <span className="capitalize">{act.severity}</span>
                  </span>
                  <span className="font-mono text-[10px] text-[var(--text-muted)]">
                    {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                <p className="font-semibold text-[var(--text-primary)]">{act.title}</p>
                <p className="text-[var(--text-secondary)] line-clamp-2">{act.description}</p>
                <div className="font-mono text-[10px] text-[var(--text-muted)] pt-1 flex items-center justify-between border-t border-[var(--border-subtle)]">
                  <span>Patient: {act.patient_id}</span>
                  <span>{act.ward_id}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
