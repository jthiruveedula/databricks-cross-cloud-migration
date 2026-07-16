import React, { useCallback, useEffect, useState } from 'react';
import RevealOnView from './motion/RevealOnView';

interface Item {
  id: string;
  label: string;
  checked?: boolean;
}

interface Props {
  title?: string;
  items: Item[];
  storageKey?: string;
}

function getStorageKey(title?: string): string | null {
  return title ? `checklist:${title.replace(/\s+/g, '-').toLowerCase()}` : null;
}

function loadState(items: Item[], key: string | null): Record<string, boolean> {
  if (typeof localStorage !== 'undefined' && key) {
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        return { ...Object.fromEntries(items.map((i) => [i.id, i.checked ?? false])), ...JSON.parse(saved) };
      }
    } catch {}
  }
  return Object.fromEntries(items.map((i) => [i.id, i.checked ?? false]));
}

export default function Checklist({ title, items, storageKey }: Props) {
  const key = storageKey ?? getStorageKey(title);
  const [state, setState] = useState<Record<string, boolean>>(() => loadState(items, key));

  useEffect(() => {
    if (key && typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(state));
    }
  }, [state, key]);

  const toggle = useCallback((id: string) => {
    setState((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const progress = Math.round((Object.values(state).filter(Boolean).length / items.length) * 100);

  return (
    <RevealOnView className="my-6 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-1">
      {title && (
        <div className="flex items-center justify-between px-4 pt-3">
          <h4 className="text-sm font-semibold text-[var(--ink)]">{title}</h4>
          <span className="text-xs text-[var(--ink-subtle)]">{progress}% complete</span>
        </div>
      )}
      <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--border)]">
        <div
          className="h-full bg-[var(--accent)] transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="p-2">
        {items.map((item) => (
          <label
            key={item.id}
            className="flex cursor-pointer items-start gap-3 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)]"
          >
            <input
              type="checkbox"
              checked={state[item.id]}
              onChange={() => toggle(item.id)}
              className="mt-1 h-4 w-4 accent-[var(--accent)]"
            />
            <span className={`text-sm ${state[item.id] ? 'text-[var(--ink-subtle)] line-through' : 'text-[var(--ink-muted)]'}`}>
              {item.label}
            </span>
          </label>
        ))}
      </div>
    </RevealOnView>
  );
}
