import React, { useId, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import RevealOnView from './motion/RevealOnView';

interface Tab {
  label: string;
  content: React.ReactNode;
}

interface Props {
  tabs: Tab[];
}

export default function Tabs({ tabs }: Props) {
  const [active, setActive] = useState(0);
  const uid = useId();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  // A tablist is expected to move focus with the arrow keys; Tab alone should
  // jump past the whole strip to the panel. Without this, reaching the last of
  // six tabs means six Tab presses.
  const onKeyDown = (event: React.KeyboardEvent) => {
    const last = tabs.length - 1;
    let next: number | null = null;
    if (event.key === 'ArrowRight') next = active === last ? 0 : active + 1;
    else if (event.key === 'ArrowLeft') next = active === 0 ? last : active - 1;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = last;
    if (next === null) return;
    event.preventDefault();
    setActive(next);
    tabRefs.current[next]?.focus();
  };

  return (
    <RevealOnView className="my-6 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] overflow-hidden">
      <div
        role="tablist"
        onKeyDown={onKeyDown}
        className="relative flex border-b border-[var(--border)] overflow-x-auto"
      >
        {tabs.map((tab, idx) => {
          const selected = active === idx;
          return (
            <button
              key={idx}
              type="button"
              role="tab"
              id={`${uid}-tab-${idx}`}
              aria-selected={selected}
              aria-controls={`${uid}-panel-${idx}`}
              // Roving tabindex: only the active tab is a tab stop.
              tabIndex={selected ? 0 : -1}
              ref={(el) => {
                tabRefs.current[idx] = el;
              }}
              onClick={() => setActive(idx)}
              className={`relative px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
                selected
                  ? 'text-[var(--accent)] bg-[var(--accent-soft)]'
                  : 'text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
              }`}
            >
              {tab.label}
              {selected && (
                <motion.div
                  // Scoped per instance: a bare "tab-indicator" is shared by
                  // every Tabs on the page, so two of them would animate the
                  // underline across from one component to the other.
                  layoutId={`${uid}-tab-indicator`}
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent)]"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
            </button>
          );
        })}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={active}
          id={`${uid}-panel-${active}`}
          role="tabpanel"
          aria-labelledby={`${uid}-tab-${active}`}
          tabIndex={0}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.15, ease: 'easeOut' }}
          className="p-4 text-sm text-[var(--ink-muted)]"
        >
          {tabs[active].content}
        </motion.div>
      </AnimatePresence>
    </RevealOnView>
  );
}
