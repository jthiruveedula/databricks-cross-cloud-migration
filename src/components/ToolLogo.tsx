import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Network } from 'lucide-react';
import BrandGlyph from '../logos/BrandGlyph';
import { BRAND_ICONS } from '../logos/brandIcons';
import { iconRegistry } from '../logos';

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [loadedIcon, setLoadedIcon] = useState<BrandIcon | null>(null);

  useEffect(() => {
    if (tool.kind === 'brand' && !loadedIcon) {
      const loadIcon = async () => {
        setLoading(true);
        setError(false);
        try {
          const icon = await iconRegistry.loadIcon(tool.icon as string);
          setLoadedIcon(icon as BrandIcon);
        } catch (err) {
          setError(true);
          console.warn(`Failed to load icon ${tool.icon} for ${name}:`, err);
        } finally {
          setLoading(false);
        }
      };
      loadIcon();
    }
  }, [tool.kind, tool.icon, name, loadedIcon]);

  const renderIcon = () => {
    if (tool.kind === 'brand' && loadedIcon && !error) {
      return <BrandGlyph icon={loadedIcon} className="h-5 w-5 text-white" />;
    }
    return React.createElement(tool.icon as React.ElementType, { className: 'h-5 w-5 text-white' });
  };

  const renderContent = () => {
    if (loading) {
      return (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="h-5 w-5 rounded bg-white/20 animate-pulse"
        />
      );
    }
    if (error) {
      return (
        <span className="text-xs text-white/80">?</span>
      );
    }
    return renderIcon();
  };

  return (
    <motion.span
      whileHover={{ scale: 1.1, boxShadow: `0 6px 20px ${tool.bg}44` }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 300, damping: 15 }}
      className={`relative inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl shadow-sm ring-1 ring-inset ring-white/15 ${className}`}
      style={{ backgroundColor: tool.bg }}
      aria-label={name}
      role="img"
    >
      <AnimatePresence mode="wait">
        {renderContent()}
      </AnimatePresence>
    </motion.span>
  );
}
