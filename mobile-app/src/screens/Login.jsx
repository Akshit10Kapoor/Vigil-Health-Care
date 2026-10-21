import React, { useState } from 'react';
import { ShieldCheck, User, Lock, AlertCircle } from 'lucide-react';
import { loginStaff } from '../services/auth_service';

export default function Login({ onLoginSuccess }) {
  const [staffId, setStaffId] = useState('ADMIN_01');
  const [password, setPassword] = useState('AdminPassword123!');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const staff = await loginStaff(staffId, password);
      onLoginSuccess(staff);
    } catch (err) {
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--canvas-bg)] flex items-center justify-center p-4">
      <div className="card-panel max-w-md w-full p-8 shadow-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-[var(--accent-teal-light)] rounded-2xl flex items-center justify-center mx-auto mb-4 text-[var(--accent-teal)] shadow-sm">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)] font-mono tracking-tight">Vigil Capture Sign In</h2>
          <p className="text-sm text-[var(--text-secondary)] mt-1">Staff Authentication & Session Start</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-[var(--severity-urgent-bg)] border border-[var(--severity-urgent-border)] text-[var(--severity-urgent-color)] rounded-lg text-sm flex items-center gap-2 font-mono">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="label-ui">Staff ID</label>
            <div className="relative">
              <User className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="text"
                required
                value={staffId}
                onChange={(e) => setStaffId(e.target.value)}
                className="input-ui !pl-10"
                placeholder="e.g. NURSE_101"
              />
            </div>
          </div>

          <div>
            <label className="label-ui">Password</label>
            <div className="relative">
              <Lock className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-ui !pl-10"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="btn-ui btn-ui-primary w-full py-3 mt-2 text-base font-semibold"
          >
            {isLoading ? 'Signing In...' : 'Sign In to Session'}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border-subtle)] text-xs text-[var(--text-secondary)] text-center">
          <p className="font-bold mb-2 uppercase tracking-wider text-[var(--text-muted)]">Demo Accounts</p>
          <p className="mt-1 font-mono text-[var(--text-primary)]">Admin/Quality: <span className="font-semibold text-[var(--accent-teal)]">ADMIN_01</span> / AdminPassword123!</p>
          <p className="mt-1 font-mono text-[var(--text-primary)]">Duty Nurse: <span className="font-semibold text-[var(--accent-teal)]">NURSE_101</span> / NursePassword123!</p>
        </div>
      </div>
    </div>
  );
}
