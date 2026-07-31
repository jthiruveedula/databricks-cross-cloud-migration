import React from 'react';
import { motion } from 'framer-motion';
import { ClipboardList, ArrowRightLeft, ShieldCheck, ArrowRight } from 'lucide-react';

interface Stage {
  label: string;
  color: string;
  icon: React.ElementType;
  desc: string;
}

// Colors borrowed from the same 7-phase language (Discovery, Data & compute migration,
// Cutover) used by PhaseShareBar/TimelineEstimator/MigrationFlowDiagram, so a reader who
// has seen those elsewhere on the site recognizes "plan / migrate / cutover" instantly.
const STAGES: Stage[] = [
  {
    label: 'Plan',
    color: '#8B5CF6',
    icon: ClipboardList,
    desc: 'Inventory, dependencies, risk, archetype — before a byte moves.',
  },
  {
    label: 'Migrate',
    color: '#10B981',
    icon: ArrowRightLeft,
    desc: 'Metastores, data, compute, pipelines, ML — moved and validated.',
  },
  {
    label: 'Validate & cutover',
    color: '#EF4444',
    icon: ShieldCheck,
    desc: 'Reconcile, verify, sign off, cut over — rollback ready.',
  },
];

export default function RunbookStagesFlow() {
  return (
    <div className="my-6 flex flex-col items-stretch gap-4 sm:flex-row sm:items-center">
      {STAGES.map((stage, i) => (
        <React.Fragment key={stage.label}>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.12, duration: 0.4 }}
            className="flex flex-1 items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-4"
          >
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
              style={{ background: `${stage.color}1A`, color: stage.color }}
            >
              <stage.icon className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-[var(--ink)]">{stage.label}</h3>
              <p className="mt-1 text-sm text-[var(--ink-muted)]">{stage.desc}</p>
            </div>
          </motion.div>
          {i < STAGES.length - 1 && (
            <div className="relative mx-auto flex shrink-0 items-center justify-center">
              <ArrowRight className="h-5 w-5 rotate-90 text-[var(--ink-subtle)] sm:rotate-0" />
              {/* Traveling glow pulse along the connector -- the same "current flows through
                  the runbook" motif as the landing page's circuit-loop background video. */}
              <motion.span
                aria-hidden="true"
                className="absolute block h-1.5 w-1.5 rounded-full sm:hidden"
                style={{ background: stage.color, boxShadow: `0 0 6px 2px ${stage.color}` }}
                animate={{ y: [-9, 9] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut', delay: i * 0.25 }}
              />
              <motion.span
                aria-hidden="true"
                className="absolute hidden h-1.5 w-1.5 rounded-full sm:block"
                style={{ background: stage.color, boxShadow: `0 0 6px 2px ${stage.color}` }}
                animate={{ x: [-9, 9] }}
                transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut', delay: i * 0.25 }}
              />
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
