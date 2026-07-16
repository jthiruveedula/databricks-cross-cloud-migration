import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Header from './Header';
import Sidebar from './Sidebar';

interface Props {
  currentSlug?: string;
  hideSidebar?: boolean;
}

// Header and Sidebar used to be mounted as two independent Astro islands, each with
// no way to reach the other's state -- the hamburger button called a no-op and the
// sidebar was permanently closed on mobile. Mounting both under one shared island
// gives them a common open/close state.
export default function AppShell({ currentSlug, hideSidebar }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(false);
  }, [currentSlug]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open]);

  return (
    <>
      <Header onMenuToggle={() => setOpen((v) => !v)} menuOpen={open} />
      {!hideSidebar && <Sidebar open={open} onClose={() => setOpen(false)} currentSlug={currentSlug} />}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
        )}
      </AnimatePresence>
    </>
  );
}
