import React, { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, X, FileText } from 'lucide-react';
import MiniSearch from 'minisearch';
import searchIndex from '../data/search-index.json';
import { withBase } from '../lib/paths';

interface Entry {
  id: number;
  slug: string;
  pageTitle: string;
  section: string;
  heading: string | null;
  headingSlug: string | null;
  text: string;
}

// Full-text search across every page's actual content, not just page titles -- the
// previous implementation only matched navigation.json titles, so a real term that only
// appears in body text (e.g. "delta", "PrivateLink", "metastore") returned nothing even
// though dozens of pages mention it. Index is generated at build/dev time by
// scripts/build-search-index.mjs from every src/pages/**/*.mdx section.
const miniSearch = new MiniSearch<Entry>({
  fields: ['pageTitle', 'heading', 'text'],
  storeFields: ['slug', 'pageTitle', 'section', 'heading', 'headingSlug', 'text'],
  searchOptions: {
    boost: { pageTitle: 3, heading: 2 },
    fuzzy: 0.2,
    prefix: true,
  },
});
miniSearch.addAll(searchIndex as Entry[]);

function excerpt(text: string, query: string): string {
  const idx = text.toLowerCase().indexOf(query.toLowerCase().split(/\s+/)[0]);
  if (idx < 0) return text.slice(0, 120) + (text.length > 120 ? '…' : '');
  const start = Math.max(0, idx - 40);
  const end = Math.min(text.length, idx + 100);
  return (start > 0 ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : '');
}

export default function SearchOverlay() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const hits = useMemo(() => {
    if (!query.trim()) return [];
    return miniSearch.search(query).slice(0, 8) as unknown as (Entry & { score: number })[];
  }, [query]);

  useEffect(() => setActiveIndex(0), [query]);

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

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  function hrefFor(hit: Entry) {
    const base = withBase(`/${hit.slug}`);
    return hit.headingSlug ? `${base}#${hit.headingSlug}` : base;
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIndex((i) => Math.min(i + 1, hits.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIndex((i) => Math.max(i - 1, 0)); }
    if (e.key === 'Enter' && hits[activeIndex]) { window.location.href = hrefFor(hits[activeIndex]); }
  }

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
      <AnimatePresence>
        {open && (
          <motion.div
            key="search-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 p-4 pt-24 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          >
            <motion.div
              key="search-modal"
              initial={{ opacity: 0, y: -12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.97 }}
              transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-xl overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
                <Search className="h-5 w-5 text-[var(--ink-subtle)]" />
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="Search migration runbook..."
                  className="flex-1 bg-transparent text-[var(--ink)] outline-none placeholder:text-[var(--ink-subtle)]"
                />
                <button onClick={() => setOpen(false)} className="text-[var(--ink-subtle)] hover:text-[var(--ink)]">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {hits.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-[var(--ink-subtle)]">
                    {query ? 'No results found.' : 'Start typing to search page titles and content.'}
                  </div>
                ) : (
                  <ul>
                    {hits.map((hit, i) => (
                      <li key={hit.id}>
                        <a
                          href={hrefFor(hit)}
                          onMouseEnter={() => setActiveIndex(i)}
                          className={`flex items-start gap-3 px-4 py-3 text-sm transition-colors ${
                            i === activeIndex ? 'bg-[var(--accent-soft)]' : 'hover:bg-[var(--surface-hover)]'
                          }`}
                        >
                          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ink-subtle)]" />
                          <span className="min-w-0 flex-1">
                            <span className="flex flex-wrap items-center gap-1.5">
                              <span className="font-medium text-[var(--ink)]">{hit.pageTitle}</span>
                              {hit.heading && (
                                <>
                                  <span className="text-[var(--ink-subtle)]">›</span>
                                  <span className="text-[var(--ink-muted)]">{hit.heading}</span>
                                </>
                              )}
                              {hit.section && (
                                <span className="ml-auto rounded-full bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--ink-subtle)]">
                                  {hit.section}
                                </span>
                              )}
                            </span>
                            <span className="mt-0.5 block truncate text-[var(--ink-subtle)]">
                              {excerpt(hit.text, query)}
                            </span>
                          </span>
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
