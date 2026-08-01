import React, { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { ShieldCheck, Cpu, Database, Workflow as WorkflowIcon } from 'lucide-react';
import BrandGlyph from './BrandGlyph';
import { BRAND_ICONS } from './logos/brandIcons';

export type ActiveCloud = 'aws' | 'azure' | 'gcp' | null;

interface Source {
  key: 'aws' | 'azure' | 'gcp';
  label: string;
  icon: keyof typeof BRAND_ICONS;
  color: string;
}

const SOURCES: Source[] = [
  { key: 'aws', label: 'AWS', icon: 'aws', color: '#FF9900' },
  { key: 'azure', label: 'Azure', icon: 'azure', color: '#0078D4' },
  { key: 'gcp', label: 'Google Cloud', icon: 'googlecloudsvg', color: '#34A853' },
];

// The four layers of the platform, in the order data actually flows through them --
// governance decides who can touch what, compute and storage do the work, orchestration
// schedules it. Same phase-color language as MigrationFlowDiagram / RunbookStagesFlow /
// TimelineEstimator elsewhere on the site, not invented per-component.
interface Layer {
  key: string;
  label: string;
  detail: string;
  color: string;
  icon: React.ElementType;
}

const LAYERS: Layer[] = [
  { key: 'governance', label: 'Governance', detail: 'Unity Catalog', color: '#8B5CF6', icon: ShieldCheck },
  { key: 'compute', label: 'Compute', detail: 'Clusters & SQL warehouses', color: '#10B981', icon: Cpu },
  { key: 'storage', label: 'Storage', detail: 'Delta Lake', color: '#3B82F6', icon: Database },
  { key: 'orchestration', label: 'Orchestration', detail: 'Workflows & DLT', color: '#F59E0B', icon: WorkflowIcon },
];

export default function MigrationDiagram({ activeCloud }: { activeCloud: ActiveCloud }) {
  const reducedMotion = useReducedMotion();
  const [pulse, setPulse] = useState(0);

  useEffect(() => {
    if (reducedMotion) return;
    const id = setInterval(() => setPulse((p) => (p + 1) % LAYERS.length), 900);
    return () => clearInterval(id);
  }, [reducedMotion]);

  const activeSource = SOURCES.find((s) => s.key === activeCloud);
  const connectorColor = activeSource?.color ?? 'var(--accent)';

  return (
    <div className="w-full max-w-md">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--ink-subtle)]">
        Databricks Lakehouse Platform
      </div>

      {/* The platform stack -- constant regardless of which cloud is underneath it. Each
          layer briefly brightens in turn so the stack itself reads as alive, distinct from
          the cloud-sync highlight below. */}
      <div className="space-y-1.5">
        {LAYERS.map((layer, i) => (
          <motion.div
            key={layer.key}
            whileHover={{ x: 3 }}
            className="flex items-center gap-3 rounded-lg border px-3 py-2 transition-colors duration-500"
            style={{
              borderColor: !reducedMotion && pulse === i ? layer.color : 'var(--border)',
              background: !reducedMotion && pulse === i ? `${layer.color}14` : 'var(--surface)',
            }}
          >
            <div
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
              style={{ background: `${layer.color}1F`, color: layer.color }}
            >
              <layer.icon className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-[var(--ink)]">{layer.label}</div>
              <div className="truncate text-xs text-[var(--ink-subtle)]">{layer.detail}</div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Connector -- a single rising thread from the active cloud into the platform,
          colored to match. Represents the workload moving up into Databricks, not a
          decorative divider. */}
      <div className="relative my-3 flex h-8 items-center justify-center">
        <div className="h-full w-px" style={{ background: `linear-gradient(to top, ${connectorColor}55, ${connectorColor})` }} />
        {!reducedMotion && (
          <motion.div
            className="absolute h-1.5 w-1.5 rounded-full"
            style={{ background: connectorColor, boxShadow: `0 0 6px 1px ${connectorColor}` }}
            animate={{ y: [14, -14], opacity: [0, 1, 0] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
      </div>

      {/* Cloud infrastructure layer -- the active one (synced to the rotating headline)
          brightens; the others settle back. */}
      <div className="flex gap-2">
        {SOURCES.map((s) => {
          const active = activeCloud === null || activeCloud === s.key;
          return (
            <div
              key={s.key}
              className="flex flex-1 items-center gap-1.5 rounded-lg border px-2 py-2 transition-all duration-300"
              style={{
                borderColor: active ? s.color : 'var(--border)',
                background: active ? `${s.color}12` : 'var(--surface)',
                opacity: active ? 1 : 0.55,
              }}
            >
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-white">
                <BrandGlyph icon={BRAND_ICONS[s.icon]} className="h-[18px] w-[18px]" brandColor />
              </div>
              <span className="truncate text-xs font-medium text-[var(--ink)]">{s.label}</span>
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-center text-xs text-[var(--ink-subtle)]">
        One platform, installed on whichever cloud you run.
      </p>
    </div>
  );
}
