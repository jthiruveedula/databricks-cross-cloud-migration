import React from 'react';
import { motion } from 'framer-motion';
import { Database, Network } from 'lucide-react';
import BrandGlyph from './logos/BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';

interface ToolDef {
  kind: 'brand' | 'lucide';
  icon: keyof typeof BRAND_ICONS | React.ElementType;
  bg: string;
}

const TOOLS: Record<string, ToolDef> = {
  'Databricks CLI': { kind: 'brand', icon: 'databricks', bg: '#FF3621' },
  UCX: { kind: 'lucide', icon: Database, bg: '#0D9488' },
  'Terraform provider': { kind: 'brand', icon: 'terraform', bg: '#844FBA' },
  'Delta Deep Clone': { kind: 'brand', icon: 'delta', bg: '#00A1DF' },
  'Delta Sharing': { kind: 'brand', icon: 'delta', bg: '#00A1DF' },
  'Cloud CLIs': { kind: 'lucide', icon: Network, bg: '#D97706' },
  GitHub: { kind: 'brand', icon: 'github', bg: '#181717' },
  MLflow: { kind: 'brand', icon: 'mlflow', bg: '#0194E2' },
  'Apache Spark': { kind: 'brand', icon: 'apachespark', bg: '#E25A1C' },
  Kubernetes: { kind: 'brand', icon: 'kubernetes', bg: '#326CE5' },
};

export default function ToolLogo({ name, className = '' }: { name: string; className?: string }) {
  const tool = TOOLS[name] ?? { kind: 'lucide' as const, icon: Database, bg: '#64748B' };
  return (
    <motion.span
      whileHover={{ scale: 1.1, boxShadow: `0 4px 16px ${tool.bg}44` }}
      transition={{ type: 'spring', stiffness: 300, damping: 15 }}
      className={`inline-flex h-10 w-10 shrink-0 cursor-default items-center justify-center rounded-xl shadow-sm ring-1 ring-inset ring-white/15 ${className}`}
      style={{ backgroundColor: tool.bg }}
      aria-label={name}
      role="img"
    >
      {tool.kind === 'brand' ? (
        <BrandGlyph icon={BRAND_ICONS[tool.icon as keyof typeof BRAND_ICONS]} className="h-5 w-5 text-white" />
      ) : (
        React.createElement(tool.icon as React.ElementType, { className: 'h-5 w-5 text-white' })
      )}
    </motion.span>
  );
}
