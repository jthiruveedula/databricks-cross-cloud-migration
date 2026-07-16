import React, { useEffect, useState } from 'react';
import ThemeToggle from './ThemeToggle';
import SearchOverlay from './SearchOverlay';
import BrandGlyph from './BrandGlyph';
import { BRAND_ICONS, type BrandIconSvg } from './logos/brandIcons';
import { withBase } from '../lib/paths';
import { Menu, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Props {
  onMenuToggle: () => void;
  menuOpen?: boolean;
}

export default function Header({ onMenuToggle, menuOpen = false }: Props) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 z-50 flex h-[var(--header-height)] w-full items-center justify-between border-b border-[var(--border)] bg-[var(--surface)]/80 px-4 backdrop-blur-md transition-shadow duration-200 lg:px-6 ${
        scrolled ? 'shadow-md' : ''
      }`}
    >
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="relative rounded-lg p-2 text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          aria-controls="primary-sidebar"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={menuOpen ? 'close' : 'menu'}
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center justify-center"
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </motion.span>
          </AnimatePresence>
        </button>
        <a href={withBase('/')} className="flex items-center gap-2 text-[var(--ink)]">
          <motion.span
            whileHover={{ rotate: -8, scale: 1.05 }}
            transition={{ type: 'spring', stiffness: 300, damping: 15 }}
            className="flex h-8 w-8 items-center justify-center rounded-lg shadow-sm"
            style={{ backgroundColor: `#${(BRAND_ICONS.databricks as BrandIconSvg).hex}` }}
          >
            <BrandGlyph icon={BRAND_ICONS.databricks} className="h-4 w-4 text-white" />
          </motion.span>
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
