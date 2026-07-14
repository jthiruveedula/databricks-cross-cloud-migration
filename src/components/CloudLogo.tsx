import React from 'react';
import { Cloud } from 'lucide-react';

type Cloud = 'aws' | 'azure' | 'gcp';

const STYLES: Record<Cloud, { bg: string; label: string }> = {
  aws: { bg: 'bg-orange-500', label: 'AWS' },
  azure: { bg: 'bg-sky-600', label: 'Azure' },
  gcp: { bg: 'bg-emerald-500', label: 'GCP' },
};

export default function CloudLogo({ cloud, className = '', showLabel = false }: { cloud: Cloud; className?: string; showLabel?: boolean }) {
  const style = STYLES[cloud];
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span
        className={`inline-flex h-12 w-12 items-center justify-center rounded-xl shadow-md ${style.bg} text-white`}
        aria-label={style.label}
      >
        <Cloud className="h-7 w-7" />
      </span>
      {showLabel && (
        <span className="text-sm font-semibold text-[var(--ink)]">{style.label}</span>
      )}
    </span>
  );
}
