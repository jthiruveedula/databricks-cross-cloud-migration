import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface Props {
  children: React.ReactNode;
  className?: string;
  /** Initial vertical offset in px before the reveal. */
  y?: number;
  /** Initial horizontal offset in px before the reveal (use instead of y, not with it). */
  x?: number;
}

/**
 * Shared scroll-reveal wrapper for content-page components (CodeBlock, Callout,
 * Checklist, Accordion, Tabs). Centralizing this means prefers-reduced-motion only
 * has to be handled once: reduced-motion users get content that's already in place
 * (no fade/slide), everyone else gets the entrance animation once, on first view.
 */
export default function RevealOnView({ children, className, y = 12, x = 0 }: Props) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y, x }}
      whileInView={{ opacity: 1, y: 0, x: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
