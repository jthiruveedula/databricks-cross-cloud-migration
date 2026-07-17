import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Search, Sun, Moon, Sidebar, HelpCircle, Hash, ArrowLeft, ArrowRight } from 'lucide-react';
import nav from '../data/navigation.json';
import { withBase } from '../lib/paths';

interface Shortcut {
  keys: string[];
  label: string;
  icon: React.ReactNode;
}

interface NavItem {
  title: string;
  slug: string;
}

const FLAT: NavItem[] = (nav as { sections: { items: NavItem[] }[] }).sections.flatMap(
  (section) => section.items
);

function currentSlug(): string {
  const base = import.meta.env.BASE_URL || '/';
  return window.location.pathname
    .replace(base, '/')
    .replace(/^\//, '')
    .replace(/\/$/, '')
    .replace(/\.html$/, '');
}

function gotoSibling(direction: 1 | -1) {
  const slug = currentSlug();
  const index = FLAT.findIndex((item) => item.slug === slug);
  if (index === -1) return;
  const target = FLAT[index + direction];
  if (target) window.location.href = withBase(`/${target.slug}/`);
}

const SHORTCUTS: Shortcut[] = [
  { keys: ['⌘K'], label: 'Search runbook', icon: <Search className="h-4 w-4" /> },
  { keys: ['t'], label: 'Toggle theme', icon: <Sun className="h-4 w-4" /> },
  { keys: ['b'], label: 'Toggle sidebar', icon: <Sidebar className="h-4 w-4" /> },
  { keys: ['j'], label: 'Next page', icon: <ArrowRight className="h-4 w-4" /> },
  { keys: ['k'], label: 'Previous page', icon: <ArrowLeft className="h-4 w-4" /> },
  { keys: ['?'], label: 'Keyboard shortcuts', icon: <HelpCircle className="h-4 w-4" /> },
  { keys: ['Esc'], label: 'Close modal / sidebar', icon: <X className="h-4 w-4" /> },
  { keys: ['1', '2', '3', '4', '5', '6', '7', '8', '9'], label: 'Jump to section (by order)', icon: <Hash className="h-4 w-4" /> },
];

const rowVariants = {
  hidden: { opacity: 0, x: -8 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: 0.1 + i * 0.04, duration: 0.2, ease: 'easeOut' },
  }),
};

export default function KeyboardShortcuts() {
  const [open, setOpen] = useState(false);

  const handler = useCallback((e: KeyboardEvent) => {
    if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      e.preventDefault();
      setOpen((v) => !v);
    }
    if (e.key === 'Escape') setOpen(false);

    if ((e.key === 'j' || e.key === 'k') && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      e.preventDefault();
      gotoSibling(e.key === 'j' ? 1 : -1);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handler]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="w-full max-w-md overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
              <h2 className="text-sm font-semibold text-[var(--ink)]">Keyboard shortcuts</h2>
              <button
                onClick={() => setOpen(false)}
                className="rounded-md p-1 text-[var(--ink-subtle)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="px-3 py-2">
              {SHORTCUTS.map((s, i) => (
                <motion.div
                  key={i}
                  custom={i}
                  initial="hidden"
                  animate="visible"
                  variants={rowVariants}
                  className="flex items-center justify-between rounded-lg px-3 py-2.5 transition-colors hover:bg-[var(--surface-hover)]"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-[var(--ink-muted)]">{s.icon}</span>
                    <span className="text-sm text-[var(--ink)]">{s.label}</span>
                  </div>
                  <kbd className="flex items-center gap-1">
                    {s.keys.map((k, j) => (
                      <span
                        key={j}
                        className="inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-xs font-medium text-[var(--ink-muted)]"
                      >
                        {k}
                      </span>
                    ))}
                  </kbd>
                </motion.div>
              ))}
            </div>
            <div className="border-t border-[var(--border)] px-5 py-2.5 text-xs text-[var(--ink-subtle)]">
              Press <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 text-xs font-medium text-[var(--ink-muted)]">?</kbd> at any time to toggle this panel.
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
