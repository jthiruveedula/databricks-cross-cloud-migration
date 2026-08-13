import React, { useId, useState } from 'react';
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
  // Stable across server and client render, and unique per instance, so two
  // accordions on one page cannot collide on ids.
  const uid = useId();

  const toggle = (idx: number) => {
    const next = new Set(open);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setOpen(next);
  };

  return (
    <RevealOnView className="my-6 divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] overflow-hidden">
      {items.map((item, idx) => {
        const isOpen = open.has(idx);
        const headerId = `${uid}-header-${idx}`;
        const panelId = `${uid}-panel-${idx}`;
        return (
          <div key={idx}>
            <button
              type="button"
              id={headerId}
              onClick={() => toggle(idx)}
              // Without aria-expanded a screen reader announces a button with
              // no indication of whether its section is open or closed.
              aria-expanded={isOpen}
              aria-controls={panelId}
              className="flex w-full items-center justify-between px-4 py-3 text-left font-medium text-[var(--ink)] hover:bg-[var(--surface-hover)]"
            >
              {item.title}
              <ChevronDown
                aria-hidden="true"
                className={`h-4 w-4 shrink-0 text-[var(--ink-subtle)] transition-transform ${isOpen ? 'rotate-180' : ''}`}
              />
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  key="content"
                  id={panelId}
                  role="region"
                  aria-labelledby={headerId}
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
        );
      })}
    </RevealOnView>
  );
}
