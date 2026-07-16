import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface Props {
  children: React.ReactNode;
  className?: string;
  /** Initial vertical offset in px before the reveal. */
  y?: number;
  /** Initial horizontal offset in px before the reveal (use instead of y, not with it). */
  x?: number;
  /** Scale factor at initial state (e.g., 0.95 for slight shrink). */
  scale?: number;
  /** Initial rotation in degrees. */
  rotate?: number;
  /** Stagger delay for children when used as a parent with staggerChildren. */
  staggerChildren?: number;
  /** Custom transition duration. */
  duration?: number;
  /** Custom viewport margin. */
  viewportMargin?: string;
  /** Whether to animate only once (default true). */
  once?: boolean;
}

const defaultVariants = {
  hidden: { opacity: 0, y: 12, x: 0, scale: 1, rotate: 0 },
  visible: { opacity: 1, y: 0, x: 0, scale: 1, rotate: 0 },
};

const parentVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
    },
  },
};

/**
 * Shared scroll-reveal wrapper for content-page components (CodeBlock, Callout,
 * Checklist, Accordion, Tabs). Centralizing this means prefers-reduced-motion only
 * has to be handled once: reduced-motion users get content that's already in place
 * (no fade/slide), everyone else gets the entrance animation once, on first view.
 */
export default function RevealOnView({
  children,
  className,
  y = 12,
  x = 0,
  scale = 1,
  rotate = 0,
  staggerChildren = 0,
  duration = 0.35,
  viewportMargin = '-40px',
  once = true,
}: Props) {
  const reduceMotion = useReducedMotion();

  // If parent provides staggerChildren, use parentVariants
  const useParentVariants = staggerChildren > 0;

  const variants = useParentVariants
    ? parentVariants
    : {
        hidden: { opacity: 0, y, x, scale, rotate },
        visible: { opacity: 1, y: 0, x: 0, scale: 1, rotate: 0 },
      };

  const initial = reduceMotion ? false : 'hidden';
  const animate = reduceMotion ? false : 'visible';
  const transition = { duration, ease: 'easeOut' };

  return (
    <motion.div
      initial={initial}
      animate={animate}
      variants={variants}
      transition={transition}
      whileInView={{ opacity: 1, y: 0, x: 0, scale: 1, rotate: 0 }}
      viewport={{ once, margin: viewportMargin }}
      className={className}
    >
      {React.Children.map(children, (child) => {
        if (!React.isValidElement(child)) return child;
        return React.cloneElement(child, {
          // Inject stagger delay for each child
          style: {
            ...(child.props.style || {}),
          },
        });
      })}
    </motion.div>
  );
}