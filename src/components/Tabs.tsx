import React, { useState } from 'react';
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

  return (
    <RevealOnView className="my-6 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] overflow-hidden">
      <div className="relative flex border-b border-[var(--border)] overflow-x-auto">
        {tabs.map((tab, idx) => (
          <button
            key={idx}
            onClick={() => setActive(idx)}
            className={`relative px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors ${
              active === idx
                ? 'text-[var(--accent)] bg-[var(--accent-soft)]'
                : 'text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
            }`}
          >
            {tab.label}
            {active === idx && (
              <motion.div
                layoutId="tab-indicator"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--accent)]"
                transition={{ type: 'spring', stiffness: 380, damping: 30 }}
              />
            )}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={active}
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
