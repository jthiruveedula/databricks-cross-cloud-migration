import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowUp } from 'lucide-react';

export default function BackToTop() {
  const [visible, setVisible] = useState(false);
  const [scrollPct, setScrollPct] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const pct = docHeight > 0 ? Math.min(window.scrollY / docHeight, 1) : 0;
      setScrollPct(pct);
      setVisible(window.scrollY > 400);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const dashoffset = circumference * (1 - scrollPct);

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="group fixed bottom-6 right-6 z-50 flex h-11 w-11 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-elevated)] text-[var(--ink-muted)] shadow-lg transition-colors hover:border-[var(--accent)]/50 hover:bg-[var(--accent-soft)] hover:text-[var(--accent)]"
          aria-label="Back to top"
        >
          {/* Progress ring */}
          <svg className="absolute inset-0 -rotate-90" width="44" height="44">
            <circle
              cx="22"
              cy="22"
              r={radius}
              fill="none"
              stroke="var(--border)"
              strokeWidth="2"
            />
            <motion.circle
              cx="22"
              cy="22"
              r={radius}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashoffset}
              initial={false}
              animate={{ strokeDashoffset: dashoffset }}
              transition={{ duration: 0.1 }}
            />
          </svg>
          <ArrowUp className="h-4 w-4 transition-transform group-hover:-translate-y-0.5" />
        </motion.button>
      )}
    </AnimatePresence>
  );
}
