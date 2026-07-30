import React, { useState, useEffect, useRef } from 'react';
import { Search, Command, ArrowRight, Activity, Users, Shield, FileText, Settings, X } from 'lucide-react';

export default function CommandPalette({ isOpen, onClose, onNavigate, wards = [], patients = [] }) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);

  // Keyboard shortcut listener for Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // Open trigger handled outside
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Build command palette options
  const defaultActions = [
    { type: 'Action', label: 'Log Nursing Round Checklist', targetTab: 'rounds', category: 'Clinical Actions', icon: Activity },
    { type: 'Action', label: 'Verify Informed Consent Form', targetTab: 'consent', category: 'Clinical Actions', icon: FileText },
    { type: 'Action', label: 'Document Medication Administration', targetTab: 'meds', category: 'Clinical Actions', icon: Activity },
    { type: 'Navigation', label: 'Jump to Ward Overview Dashboard', targetTab: 'dashboard', category: 'Views', icon: Shield },
    { type: 'Navigation', label: 'Open Gap History & Audit Log', targetTab: 'gaps', category: 'Views', icon: Shield },
    { type: 'Navigation', label: 'Open Patient Registry', targetTab: 'patients', category: 'Views', icon: Users },
    { type: 'Navigation', label: 'Generate & Export NABH Audit Evidence', targetTab: 'evidence', category: 'Audit Pack', icon: FileText },
    { type: 'Navigation', label: 'Hospital Settings & Role Configuration', targetTab: 'settings', category: 'System', icon: Settings },
  ];

  const wardItems = wards.map(w => ({
    type: 'Ward',
    label: `Filter by Ward: ${w.name} (${w.ward_id})`,
    targetTab: 'dashboard',
    category: 'Wards',
    icon: Shield,
    ward_id: w.ward_id
  }));

  const patientItems = patients.map(p => ({
    type: 'Patient',
    label: `Patient: ${p.full_name} (${p.patient_id}) — Bed ${p.bed_number}`,
    targetTab: 'patients',
    category: 'Patients',
    icon: Users,
    patient_id: p.patient_id
  }));

  const allItems = [...defaultActions, ...wardItems, ...patientItems];

  const filteredItems = allItems.filter(item =>
    item.label.toLowerCase().includes(query.toLowerCase()) ||
    item.category.toLowerCase().includes(query.toLowerCase())
  );

  const handleKeyDownInMenu = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % Math.max(1, filteredItems.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredItems[selectedIndex]) {
        executeCommand(filteredItems[selectedIndex]);
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  const executeCommand = (item) => {
    onNavigate(item.targetTab, item);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-start justify-center pt-20 p-4">
      <div className="bg-[var(--card-bg)] border border-[var(--border-medium)] w-full max-w-xl rounded-xl shadow-2xl overflow-hidden flex flex-col animate-fade-in">
        {/* Input Header */}
        <div className="p-3.5 border-b border-[var(--border-subtle)] flex items-center gap-3">
          <Search className="w-5 h-5 text-[var(--text-muted)] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDownInMenu}
            placeholder="Type a command, search ward, or jump to patient..."
            className="w-full bg-transparent text-sm text-[var(--text-primary)] outline-none font-medium placeholder-[var(--text-muted)]"
          />
          <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filteredItems.length === 0 ? (
            <div className="p-6 text-center text-xs text-[var(--text-muted)] font-mono">
              No matching commands or records found for "{query}"
            </div>
          ) : (
            filteredItems.map((item, index) => {
              const Icon = item.icon;
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={`${item.type}-${index}`}
                  onClick={() => executeCommand(item)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs cursor-pointer transition ${
                    isSelected ? 'bg-[var(--accent-teal-light)] text-[var(--accent-teal)] font-semibold' : 'text-[var(--text-secondary)] hover:bg-[var(--card-hover)]'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isSelected ? 'text-[var(--accent-teal)]' : 'text-[var(--text-muted)]'}`} />
                    <span>{item.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-[var(--canvas-bg)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                      {item.category}
                    </span>
                    {isSelected && <ArrowRight className="w-3.5 h-3.5 text-[var(--accent-teal)]" />}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Shortcut Info */}
        <div className="px-4 py-2 bg-[var(--canvas-bg)] border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] font-mono text-[var(--text-muted)]">
          <span>Navigate <kbd className="px-1 bg-[var(--card-bg)] rounded border">↑</kbd> <kbd className="px-1 bg-[var(--card-bg)] rounded border">↓</kbd></span>
          <span>Select <kbd className="px-1 bg-[var(--card-bg)] rounded border">↵</kbd></span>
          <span>Close <kbd className="px-1 bg-[var(--card-bg)] rounded border">esc</kbd></span>
        </div>
      </div>
    </div>
  );
}
