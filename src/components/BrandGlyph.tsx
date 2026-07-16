import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { BrandIcon, BrandIconImage, BrandIconSvg } from './logos/brandIcons';

interface Props {
  icon: BrandIcon;
  className?: string;
  brandColor?: boolean;
}

function ImageGlyph({ icon, className, brandColor }: Props & { icon: BrandIconImage }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  return (
    <motion.div
      whileHover={{ scale: 1.08, rotate: brandColor ? 6 : 0 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className="inline-flex items-center justify-center"
      style={{ width: icon.width, height: icon.height }}
    >
      <AnimatePresence>
        {!loaded && !error && (
          <motion.div
            key="skeleton"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute h-5 w-5 rounded bg-[var(--border)] animate-pulse"
          />
        )}
      </AnimatePresence>
      {error ? (
        <div
          className="inline-flex items-center justify-center h-5 w-5 text-[var(--ink-subtle)]"
          role="img"
          aria-label={`${keyFromUrl(icon.url)} icon (failed to load)`}
        >
          <span className="text-xs">?</span>
        </div>
      ) : (
        <img
          src={icon.url}
          width={icon.width}
          height={icon.height}
          className={`${className} ${!loaded ? 'hidden' : 'block'}`}
          style={{ display: loaded ? 'block' : 'none' }}
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
          alt=""
        />
      )}
    </motion.div>
  );
}

function SvgGlyph({ icon, className, brandColor }: Props & { icon: BrandIconSvg }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoaded(false);
    setError(false);
    const img = new Image();
    img.onload = () => setLoaded(true);
    img.onerror = () => setError(true);
    img.src = `data:image/svg+xml;base64,${btoa(icon.path)}`;
  }, [icon.path]);

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
        style={{ display: loaded ? 'block' : 'none' }}
      >
        <title>{icon.title}</title>
        <path d={icon.path} />
      </svg>
    </motion.div>
  );
}

function keyFromUrl(url: string): string {
  try {
    const path = new URL(url).pathname;
    const last = path.split('/').pop() || '';
    return last.replace(/\.[^.]+$/, '');
  } catch {
    return 'icon';
  }
}

export default function BrandGlyph({ icon, className = 'h-5 w-5', brandColor = false }: Props) {
  if (icon.type === 'image') {
    return <ImageGlyph icon={icon} className={className} brandColor={brandColor} />;
  }
  return <SvgGlyph icon={icon} className={className} brandColor={brandColor} />;
}