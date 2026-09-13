import React, { lazy, Suspense, useEffect, useState } from 'react';
import { Search } from 'lucide-react';

// The actual search UI + MiniSearch index (~460KB of search-index.json alone)
// used to be a static import here, which meant EVERY page shipped the full
// index in its shared shell bundle whether or not the visitor ever searched.
// Lazy-loading means the heavy chunk only fetches on first ⌘K / click --
// this component is the always-eager part: two buttons and a key listener,
// nothing else.
const SearchOverlayModal = lazy(() => import('./SearchOverlayModal'));

export default function SearchTrigger() {
  const [open, setOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setEverOpened(true);
        setOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  function handleOpen() {
    setEverOpened(true);
    setOpen(true);
  }

  return (
    <>
      <button
        onClick={handleOpen}
        className="hidden items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1.5 text-sm text-[var(--ink-subtle)] transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--ink)] sm:flex"
      >
        <Search className="h-4 w-4" />
        <span>Search</span>
        <kbd className="ml-2 rounded border border-[var(--border)] px-1.5 py-0.5 text-xs">⌘K</kbd>
      </button>
      <button
        onClick={handleOpen}
        className="rounded-lg p-2 text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] sm:hidden"
        aria-label="Search"
      >
        <Search className="h-5 w-5" />
      </button>
      {everOpened && (
        <Suspense fallback={null}>
          <SearchOverlayModal open={open} onClose={() => setOpen(false)} />
        </Suspense>
      )}
    </>
  );
}
