import React from 'react';
import { motion } from 'framer-motion';
import nav from '../data/navigation.json';
import { withBase } from '../lib/paths';
import { ChevronRight } from 'lucide-react';

interface Props {
  open: boolean;
  onClose: () => void;
  currentSlug?: string;
}

const sectionVariants = {
  hidden: { opacity: 0, x: -8 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.04, duration: 0.2, ease: 'easeOut' },
  }),
};

export default function Sidebar({ open, onClose, currentSlug }: Props) {
  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`
          fixed inset-0 z-40 bg-black/20 backdrop-blur-sm transition-opacity duration-300
          ${open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'}
        `}
      />
      <aside
        id="primary-sidebar"
        role="dialog"
        aria-modal="true"
        aria-label="Site navigation"
        aria-hidden={!open}
        className={`
          fixed left-0 top-[var(--header-height)] z-50 h-[calc(100vh-var(--header-height))] w-[var(--sidebar-width)]
          transform border-r border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-md
          transition-transform duration-300 ease-in-out
          ${open ? 'translate-x-0' : '-translate-x-full'}
          sidebar-scroll overflow-y-auto pb-8
        `}
      >
        <nav className="px-3 py-4">
          {nav.sections.map((section, sectionIdx) => (
            <motion.div
              key={section.slug}
              className="mb-5"
              custom={sectionIdx}
              initial="hidden"
              animate={open ? 'visible' : 'hidden'}
              variants={sectionVariants}
            >
              <div className="mb-2 flex items-center gap-1 px-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-subtle)]">
                {section.title}
              </div>
              <ul className="space-y-0.5">
                {section.items.map((item) => {
                  const slug = `/${item.slug}`;
                  const active = currentSlug === item.slug || currentSlug === slug;
                  return (
                    <li key={item.slug}>
                      <a
                        href={withBase(slug)}
                        onClick={onClose}
                        className={`
                          relative flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors
                          ${active ? 'bg-[var(--accent-soft)] font-medium text-[var(--accent)]' : 'text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'}
                        `}
                      >
                        {active && (
                          <motion.span
                            layoutId="sidebar-active-indicator"
                            className="absolute left-0 top-1 bottom-1 w-0.5 rounded-full bg-[var(--accent)]"
                            transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                          />
                        )}
                        {item.title}
                        {active && <ChevronRight className="h-3.5 w-3.5" />}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </motion.div>
          ))}
        </nav>
      </aside>
    </>
  );
}
