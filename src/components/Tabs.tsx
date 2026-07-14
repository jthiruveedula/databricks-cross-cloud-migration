import React, { useState } from 'react';

interface Tab {
  label: string;
  content: React.ReactNode;
}

interface Props {
  tabs: Tab[];
}

export default function Tabs({ tabs }: Props) {
  const [active, setActive] = useState(0);

  return (
    <div className="my-6 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] overflow-hidden">
      <div className="flex border-b border-[var(--border)] overflow-x-auto">
        {tabs.map((tab, idx) => (
          <button
            key={idx}
            onClick={() => setActive(idx)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
              active === idx
                ? 'text-[var(--accent)] border-b-2 border-[var(--accent)] bg-[var(--accent-soft)]'
                : 'text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="p-4 text-sm text-[var(--ink-muted)]">{tabs[active].content}</div>
    </div>
  );
}
