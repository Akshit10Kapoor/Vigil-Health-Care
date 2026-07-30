import React, { useState, useEffect, useRef } from 'react';
import { Search, ChevronDown, Check } from 'lucide-react';

export default function TypeaheadCombobox({ options, selectedValue, onSelect, placeholder = "Search patient..." }) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const wrapperRef = useRef(null);

  const selectedOption = options.find(o => o.value === selectedValue);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredOptions = options.filter(o =>
    o.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (o.sublabel && o.sublabel.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div ref={wrapperRef} className="relative w-full">
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="input-ui flex items-center justify-between cursor-pointer font-medium"
      >
        <span className="truncate">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <ChevronDown className="w-4 h-4 text-[var(--text-muted)] shrink-0 ml-2" />
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--card-bg)] border border-[var(--border-medium)] rounded-lg shadow-xl z-50 overflow-hidden max-h-60 flex flex-col">
          <div className="p-2 border-b border-[var(--border-subtle)] flex items-center gap-2">
            <Search className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
            <input
              type="text"
              autoFocus
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Type patient name, ID, or bed..."
              className="w-full bg-transparent text-xs text-[var(--text-primary)] outline-none"
            />
          </div>

          <div className="overflow-y-auto p-1 space-y-0.5">
            {filteredOptions.length === 0 ? (
              <div className="p-3 text-center text-xs text-[var(--text-muted)]">No matching options</div>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = opt.value === selectedValue;
                return (
                  <div
                    key={opt.value}
                    onClick={() => {
                      onSelect(opt.value);
                      setIsOpen(false);
                      setSearchTerm('');
                    }}
                    className={`flex items-center justify-between px-3 py-2 rounded-md text-xs cursor-pointer ${
                      isSelected ? 'bg-[var(--accent-teal-light)] text-[var(--accent-teal)] font-semibold' : 'text-[var(--text-primary)] hover:bg-[var(--card-hover)]'
                    }`}
                  >
                    <div>
                      <p>{opt.label}</p>
                      {opt.sublabel && <p className="text-[10px] text-[var(--text-muted)] font-mono">{opt.sublabel}</p>}
                    </div>
                    {isSelected && <Check className="w-3.5 h-3.5 text-[var(--accent-teal)]" />}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
