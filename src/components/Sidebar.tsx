import React from 'react';
import nav from '../data/navigation.json';
import { ChevronRight } from 'lucide-react';

interface Props {
  open: boolean;
  onClose: () => void;
  currentSlug?: string;
}

export default function Sidebar({ open, onClose, currentSlug }: Props) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        id="primary-sidebar"
        className={`
          fixed left-0 top-[var(--header-height)] z-50 h-[calc(100vh-var(--header-height))] w-[var(--sidebar-width)]
          transform border-r border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur-md
          transition-transform duration-300 lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          overflow-y-auto pb-8
        `}
      >
        <nav className="px-3 py-4">
          {nav.sections.map((section) => (
            <div key={section.slug} className="mb-5">
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
                        href={slug}
                        onClick={onClose}
                        className={`
                          flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors
                          ${active ? 'bg-[var(--accent-soft)] font-medium text-[var(--accent)]' : 'text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'}
                        `}
                      >
                        {item.title}
                        {active && <ChevronRight className="h-3.5 w-3.5" />}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
