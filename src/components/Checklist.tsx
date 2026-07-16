import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check } from 'lucide-react';
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

  const checkedCount = Object.values(state).filter(Boolean).length;
  const progress = Math.round((checkedCount / items.length) * 100);
  const isComplete = progress === 100;

  return (
    <RevealOnView className="my-6 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-1">
      {title && (
        <div className="flex items-center justify-between px-4 pt-3">
          <h4 className="text-sm font-semibold text-[var(--ink)]">{title}</h4>
          <AnimatePresence mode="wait">
            <motion.span
              key={isComplete ? 'done' : 'pct'}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className={`text-xs ${isComplete ? 'font-medium text-emerald-500' : 'text-[var(--ink-subtle)]'}`}
            >
              {isComplete ? 'All done!' : `${progress}% complete`}
            </motion.span>
          </AnimatePresence>
        </div>
      )}
      <div className="relative h-1 w-full overflow-hidden rounded-full bg-[var(--border)]">
        <motion.div
          className={`h-full rounded-full transition-colors duration-500 ${
            isComplete ? 'bg-emerald-500' : 'bg-[var(--accent)]'
          }`}
          initial={false}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
        {isComplete && (
          <motion.div
            className="absolute inset-0 rounded-full bg-emerald-400/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.6, 0] }}
            transition={{ duration: 1.5, ease: 'easeInOut' }}
          />
        )}
      </div>
      <div className="p-2">
        {items.map((item, idx) => (
          <motion.label
            key={item.id}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.03 }}
            className="flex cursor-pointer items-start gap-3 rounded-lg p-2 transition-colors hover:bg-[var(--surface-hover)]"
          >
            {/* Custom animated checkbox */}
            <button
              type="button"
              role="checkbox"
              aria-checked={state[item.id]}
              onClick={() => toggle(item.id)}
              className={`relative mt-0.5 flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-md border-2 transition-all duration-200 ${
                state[item.id]
                  ? 'border-[var(--accent)] bg-[var(--accent)]'
                  : 'border-[var(--ink-subtle)] bg-transparent hover:border-[var(--accent)]/50'
              }`}
            >
              <AnimatePresence>
                {state[item.id] && (
                  <motion.span
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0, opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 25 }}
                  >
                    <Check className="h-3 w-3 text-white" strokeWidth={3} />
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
            <motion.span
              animate={{
                color: state[item.id] ? 'var(--ink-subtle)' : 'var(--ink-muted)',
              }}
              className={`text-sm ${state[item.id] ? 'line-through decoration-[var(--accent)]/40' : ''}`}
            >
              {item.label}
            </motion.span>
          </motion.label>
        ))}
      </div>
    </RevealOnView>
  );
}
