import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { BrandIcon } from './brandIcons';

interface Props {
  icon: BrandIcon;
  className?: string;
  /** Render the glyph in the brand's own color instead of currentColor. */
  brandColor?: boolean;
}

export default function BrandGlyph({ icon, className = 'h-5 w-5', brandColor = false }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoaded(false);
    setError(false);
    
    const img = new Image();
    img.onload = () => setLoaded(true);
    img.onerror = () => setError(true);
    img.src = `data:image/svg+xml;base64,${btoa(icon.path)}`;
  }, [icon.id]);

  if (error) {
    return (
      <div
        className="inline-flex items-center justify-center h-5 w-5 text-[var(--ink-subtle)]"
        role="img"
        aria-label={`${icon.title} icon (failed to load)`}
      >
        <span className="text-xs">?</span>
      </div>
    );
  }

  return (
    <motion.div
      whileHover={{ scale: 1.08, rotate: brandColor ? 6 : 0 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className="inline-flex items-center justify-center"
    >
      <AnimatePresence>
        {!loaded && (
          <motion.div
            key="skeleton"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute h-5 w-5 rounded bg-[var(--border)] animate-pulse"
          />
        )}
      </AnimatePresence>
      <svg
        role="img"
        viewBox="0 0 24 24"
        className={`h-full w-full ${className} ${!loaded ? 'hidden' : 'block'}`}
        fill={brandColor ? `#${icon.hex}` : 'currentColor'}
        aria-hidden="true"
        onLoad={() => setLoaded(true)}
        onError={() => setError(true)}
        style={{ display: loaded ? 'block' : 'none' }}
      >
        <title>{icon.title}</title>
        <path
          onError={() => setError(true)}
          d={icon.path}
        />
      </svg>
    </motion.div>
  );
}
