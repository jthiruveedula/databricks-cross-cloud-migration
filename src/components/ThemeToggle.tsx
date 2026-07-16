import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Moon, Sun } from 'lucide-react';

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = saved === 'dark' || (!saved && prefersDark);
    setDark(isDark);
    if (isDark) root.classList.add('dark');
    else root.classList.remove('dark');
  }, []);

  const toggle = () => {
    const root = document.documentElement;
    const next = !dark;
    setDark(next);
    // Smooth transition: add class, toggle theme, remove after animation
    root.classList.add('theme-transitioning');
    if (next) {
      root.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
    setTimeout(() => root.classList.remove('theme-transitioning'), 300);
  };

  return (
    <button
      onClick={toggle}
      className="relative rounded-lg p-2 text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
      aria-label="Toggle theme"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={dark ? 'sun' : 'moon'}
          initial={{ rotate: -90, scale: 0, opacity: 0 }}
          animate={{ rotate: 0, scale: 1, opacity: 1 }}
          exit={{ rotate: 90, scale: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="flex items-center justify-center"
        >
          {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}
