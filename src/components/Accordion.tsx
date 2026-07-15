import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import RevealOnView from './motion/RevealOnView';

interface Item {
  title: string;
  content: React.ReactNode;
}

interface Props {
  items: Item[];
  defaultOpen?: number[];
}

export default function Accordion({ items, defaultOpen = [] }: Props) {
  const [open, setOpen] = useState<Set<number>>(new Set(defaultOpen));

  const toggle = (idx: number) => {
    const next = new Set(open);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setOpen(next);
  };

  return (
    <RevealOnView className="my-6 divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] overflow-hidden">
      {items.map((item, idx) => (
        <div key={idx}>
          <button
            onClick={() => toggle(idx)}
            className="flex w-full items-center justify-between px-4 py-3 text-left font-medium text-[var(--ink)] hover:bg-[var(--surface-hover)]"
          >
            {item.title}
            <ChevronDown className={`h-4 w-4 text-[var(--ink-subtle)] transition-transform ${open.has(idx) ? 'rotate-180' : ''}`} />
          </button>
          <AnimatePresence initial={false}>
            {open.has(idx) && (
              <motion.div
                key="content"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
                className="overflow-hidden"
              >
                <div className="px-4 pb-4 text-sm text-[var(--ink-muted)]">{item.content}</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </RevealOnView>
  );
}
