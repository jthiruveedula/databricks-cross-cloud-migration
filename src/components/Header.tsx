import React from 'react';
import ThemeToggle from './ThemeToggle';
import SearchOverlay from './SearchOverlay';
import { Menu, Cloud, Github } from 'lucide-react';

interface Props {
  onMenuToggle: () => void;
}

export default function Header({ onMenuToggle }: Props) {
  return (
    <header className="fixed top-0 z-50 flex h-[var(--header-height)] w-full items-center justify-between border-b border-[var(--border)] bg-[var(--surface)]/80 px-4 backdrop-blur-md lg:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="rounded-lg p-2 text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] lg:hidden"
          aria-label="Open sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <a href="/" className="flex items-center gap-2 text-[var(--ink)]">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--accent)] to-violet-500 text-white">
            <Cloud className="h-5 w-5" />
          </div>
          <span className="hidden font-semibold tracking-tight sm:inline">Databricks Migration Runbook</span>
        </a>
      </div>
      <div className="flex items-center gap-2">
        <SearchOverlay />
        <ThemeToggle />
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg p-2 text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
          aria-label="GitHub"
        >
          <Github className="h-5 w-5" />
        </a>
      </div>
    </header>
  );
}
