import React from 'react';
import { motion } from 'framer-motion';
import BrandGlyph from './logos/BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';

type Cloud = 'aws' | 'azure' | 'gcp';

interface CloudStyle {
  label: string;
  bg: string;
  ring: string;
}

// AWS and Microsoft Azure marks are trademark-restricted and not redistributed by icon
// libraries, so those two render as clean brand-color wordmark badges. GCP's mark is
// published under Google's open terms (via simple-icons), so it renders as the real glyph.
const STYLES: Record<Cloud, CloudStyle> = {
  aws: { label: 'AWS', bg: '#FF9900', ring: 'rgba(255,153,0,0.35)' },
  azure: { label: 'Azure', bg: '#0078D4', ring: 'rgba(0,120,212,0.35)' },
  gcp: { label: 'GCP', bg: '#4285F4', ring: 'rgba(66,133,244,0.35)' },
};

export default function CloudLogo({
  cloud,
  className = '',
  showLabel = false,
  size = 'md',
}: {
  cloud: Cloud;
  className?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}) {
  const style = STYLES[cloud];
  const dims = size === 'sm' ? 'h-8 w-8' : size === 'lg' ? 'h-14 w-14' : 'h-12 w-12';
  const textSize = size === 'sm' ? 'text-[9px]' : size === 'lg' ? 'text-sm' : 'text-xs';

  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <motion.span
        whileHover={{ scale: 1.1, boxShadow: `0 6px 24px ${style.ring}` }}
        transition={{ type: 'spring', stiffness: 300, damping: 15 }}
        className={`inline-flex shrink-0 cursor-default items-center justify-center rounded-xl shadow-md ring-1 ring-inset ring-white/15 ${dims}`}
        style={{ backgroundColor: style.bg, boxShadow: `0 4px 14px ${style.ring}` }}
        aria-label={`${style.label} logo`}
        role="img"
      >
        {cloud === 'gcp' ? (
          <BrandGlyph icon={BRAND_ICONS.googlecloud} className="h-6 w-6 text-white" />
        ) : (
          <span className={`font-bold uppercase tracking-tight text-white ${textSize}`}>{style.label}</span>
        )}
      </motion.span>
      {showLabel && <span className="text-sm font-semibold text-[var(--ink)]">{style.label}</span>}
    </span>
  );
}
