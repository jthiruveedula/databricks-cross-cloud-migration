import React from 'react';
import type { BrandIcon } from './brandIcons';

interface Props {
  icon: BrandIcon;
  className?: string;
  /** Render the glyph in the brand's own color instead of currentColor. */
  brandColor?: boolean;
}

export default function BrandGlyph({ icon, className = 'h-5 w-5', brandColor = false }: Props) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      className={className}
      fill={brandColor ? `#${icon.hex}` : 'currentColor'}
      aria-hidden="true"
    >
      <title>{icon.title}</title>
      <path d={icon.path} />
    </svg>
  );
}
