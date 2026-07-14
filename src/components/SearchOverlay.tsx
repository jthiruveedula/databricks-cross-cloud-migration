import React, { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import nav from '../data/navigation.json';

interface Hit {
  title: string;
  slug: string;
  section: string;
}

export default function SearchOverlay() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const hits = useMemo<Hit[]>(() => {
    const q = query.toLowerCase();
    if (!q) return [];
    return nav.sections.flatMap((section) =>
      section.items
        .filter((item) => item.title.toLowerCase().includes(q) || section.title.toLowerCase().includes(q))
        .map((item) => ({ title: item.title, slug: `/${item.slug}`, section: section.title }))
    );
  }, [query]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="hidden items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1.5 text-sm text-[var(--ink-subtle)] transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--ink)] sm:flex"
      >
        <Search className="h-4 w-4" />
        <span>Search</span>
        <kbd className="ml-2 rounded border border-[var(--border)] px-1.5 py-0.5 text-xs">⌘K</kbd>
      </button>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg p-2 text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] sm:hidden"
        aria-label="Search"
      >
        <Search className="h-5 w-5" />
      </button>
      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 p-4 pt-24 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-xl overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              <Search className="h-5 w-5 text-[var(--ink-subtle)]" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search migration runbook..."
                className="flex-1 bg-transparent text-[var(--ink)] outline-none placeholder:text-[var(--ink-subtle)]"
              />
              <button onClick={() => setOpen(false)} className="text-[var(--ink-subtle)] hover:text-[var(--ink)]">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto">
              {hits.length === 0 ? (
                <div className="px-4 py-6 text-center text-sm text-[var(--ink-subtle)]">
                  {query ? 'No results found.' : 'Start typing to search pages.'}
                </div>
              ) : (
                <ul>
                  {hits.map((hit, i) => (
                    <li key={i}>
                      <a
                        href={hit.slug}
                        className="block px-4 py-3 hover:bg-[var(--surface-hover)]"
                        onClick={() => setOpen(false)}
                      >
                        <div className="text-sm font-medium text-[var(--ink)]">{hit.title}</div>
                        <div className="text-xs text-[var(--ink-subtle)]">{hit.section}</div>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
