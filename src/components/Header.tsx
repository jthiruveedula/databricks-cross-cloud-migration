import React from 'react';
import ThemeToggle from './ThemeToggle';
import SearchOverlay from './SearchOverlay';
import BrandGlyph from './logos/BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';
import { Menu, X } from 'lucide-react';

interface Props {
  onMenuToggle: () => void;
  menuOpen?: boolean;
}

export default function Header({ onMenuToggle, menuOpen = false }: Props) {
  return (
    <header className="fixed top-0 z-50 flex h-[var(--header-height)] w-full items-center justify-between border-b border-[var(--border)] bg-[var(--surface)]/80 px-4 backdrop-blur-md lg:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="rounded-lg p-2 text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] lg:hidden"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          aria-controls="primary-sidebar"
        >
          {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <a href="/" className="flex items-center gap-2 text-[var(--ink)]">
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg shadow-sm"
            style={{ backgroundColor: `#${BRAND_ICONS.databricks.hex}` }}
          >
            <BrandGlyph icon={BRAND_ICONS.databricks} className="h-4 w-4 text-white" />
          </span>
          <span className="hidden font-semibold tracking-tight sm:inline">Databricks Migration Runbook</span>
        </a>
      </div>
      <div className="flex items-center gap-2">
        <SearchOverlay />
        <ThemeToggle />
        <a
          href="https://github.com/jthiruveedula/databricks-cross-cloud-migration"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg p-2 text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
          aria-label="View source on GitHub"
        >
          <BrandGlyph icon={BRAND_ICONS.github} className="h-5 w-5" />
        </a>
      </div>
    </header>
  );
}
