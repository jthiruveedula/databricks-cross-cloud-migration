import React from 'react';
import { motion } from 'framer-motion';
import {
  Merge,
  MapPin,
  DollarSign,
  Boxes,
  ClipboardList,
  GitBranch,
  ShieldAlert,
  KeyRound,
  Network,
  ShieldCheck,
  Database,
  Cpu,
  Workflow as WorkflowIcon,
  ArrowLeftRight,
  RotateCcw,
} from 'lucide-react';

export type ChapterKey = 'trigger' | 'assess' | 'blueprint' | 'move' | 'cutover';

// One color per chapter, drawn from the same 7-phase palette used by MigrationFlowDiagram /
// RunbookStagesFlow / TimelineEstimator / the hero diagram elsewhere on the site -- so a
// reader who has seen the palette anywhere else on the site recognizes it here too.
export const CHAPTER_COLOR: Record<ChapterKey, string> = {
  trigger: '#8B5CF6',
  assess: '#3B82F6',
  blueprint: '#10B981',
  move: '#F59E0B',
  cutover: '#EF4444',
};

function Chip({ icon: Icon, label, color }: { icon: React.ElementType; label: string; color: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border px-3 py-2" style={{ borderColor: `${color}55`, background: `${color}12` }}>
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded" style={{ background: `${color}22`, color }}>
        <Icon className="h-3.5 w-3.5" />
      </div>
      <span className="text-xs font-medium text-[var(--ink)]">{label}</span>
    </div>
  );
}

function Row({ icon: Icon, label, detail, color }: { icon: React.ElementType; label: string; detail: string; color: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border px-3 py-2" style={{ borderColor: `${color}55`, background: `${color}0d` }}>
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md" style={{ background: `${color}22`, color }}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-[var(--ink)]">{label}</div>
        <div className="truncate text-xs text-[var(--ink-subtle)]">{detail}</div>
      </div>
    </div>
  );
}

function Panel({ label, color, children }: { label: string; color: string; children: React.ReactNode }) {
  return (
    <div className="w-full max-w-xs rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-5 shadow-card lg:max-w-sm">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wide" style={{ color }}>
        {label}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

// Each chapter gets a small diagram of what that chapter is actually about -- the real
// drivers, the real dependency graph, the real landing-zone layers, the real migration
// waves, the real cutover swap -- instead of one ambient background shared by all five.
export default function JourneyVisual({ chapterKey }: { chapterKey: ChapterKey }) {
  const color = CHAPTER_COLOR[chapterKey];

  const content = (() => {
    switch (chapterKey) {
      case 'trigger':
        return (
          <Panel label="Common triggers" color={color}>
            <div className="grid grid-cols-2 gap-2">
              <Chip icon={Merge} label="Merger" color={color} />
              <Chip icon={MapPin} label="Data residency" color={color} />
              <Chip icon={DollarSign} label="Cost cliff" color={color} />
              <Chip icon={Boxes} label="Consolidation" color={color} />
            </div>
          </Panel>
        );
      case 'assess':
        return (
          <Panel label="What gets inventoried" color={color}>
            <Row icon={ClipboardList} label="Inventory" detail="Workspaces, catalogs, jobs, notebooks" color={color} />
            <Row icon={GitBranch} label="Dependencies" detail="What breaks if this moves first" color={color} />
            <Row icon={ShieldAlert} label="Risk" detail="Scored, not guessed" color={color} />
          </Panel>
        );
      case 'blueprint':
        return (
          <Panel label="Target landing zone" color={color}>
            <Row icon={KeyRound} label="Identity" detail="Federated, not recreated" color={color} />
            <Row icon={Network} label="Network" detail="Private connectivity, egress control" color={color} />
            <Row icon={ShieldCheck} label="Unity Catalog" detail="Single governance plane" color={color} />
          </Panel>
        );
      case 'move':
        return (
          <Panel label="Moved in waves" color={color}>
            <div className="flex items-center justify-between gap-1">
              <Chip icon={Database} label="Storage" color={color} />
              <span className="text-xs" style={{ color }}>→</span>
              <Chip icon={Cpu} label="Compute" color={color} />
              <span className="text-xs" style={{ color }}>→</span>
              <Chip icon={WorkflowIcon} label="Pipelines" color={color} />
            </div>
          </Panel>
        );
      case 'cutover':
        return (
          <Panel label="Blue-green cutover" color={color}>
            <Row icon={ArrowLeftRight} label="Traffic switch" detail="Source live → target live" color={color} />
            <Row icon={ShieldCheck} label="Reconciliation" detail="Data + business UAT sign-off" color={color} />
            <Row icon={RotateCcw} label="Rollback" detail="One command away throughout" color={color} />
          </Panel>
        );
    }
  })();

  return (
    <motion.div
      key={chapterKey}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
    >
      {content}
    </motion.div>
  );
}
