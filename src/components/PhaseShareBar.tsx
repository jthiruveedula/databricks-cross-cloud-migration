import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Phase {
  label: string;
  color: string;
  min: number;
  max: number;
}

// Same seven phases, same hex values as TimelineEstimator/MigrationFlowDiagram --
// one color language for "migration phase" everywhere on the site.
const PHASES: Phase[] = [
  { label: 'Discovery', color: '#8B5CF6', min: 10, max: 15 },
  { label: 'Foundation', color: '#3B82F6', min: 15, max: 20 },
  { label: 'Data & compute migration', color: '#10B981', min: 30, max: 40 },
  { label: 'Pipeline migration', color: '#F59E0B', min: 10, max: 15 },
  { label: 'Validation', color: '#F97316', min: 10, max: 15 },
  { label: 'Cutover', color: '#EF4444', min: 5, max: 10 },
  { label: 'Hypercare', color: '#EC4899', min: 5, max: 10 },
];

export default function PhaseShareBar() {
  const [active, setActive] = useState<number | null>(null);
  // Use each phase's midpoint share to size its segment -- the min-max range still
  // shows in the tooltip/legend, the bar itself reads at a single glance.
  const mids = PHASES.map((p) => (p.min + p.max) / 2);
  const total = mids.reduce((a, b) => a + b, 0);

  return (
    <div className="my-6">
      <div className="flex h-10 overflow-hidden rounded-lg border border-[var(--border)]">
        {PHASES.map((phase, i) => (
          <motion.button
            key={phase.label}
            type="button"
            onMouseEnter={() => setActive(i)}
            onFocus={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
            onBlur={() => setActive(null)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: i * 0.05 }}
            style={{ width: `${(mids[i] / total) * 100}%`, background: phase.color }}
            className="relative flex items-center justify-center text-[11px] font-semibold text-white transition-[filter] hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            aria-label={`${phase.label}: ${phase.min}–${phase.max}% of timeline`}
          >
            <span className="hidden truncate px-1 sm:inline">{i + 1}</span>
          </motion.button>
        ))}
      </div>

      <div className="relative mt-3 min-h-[2.5rem]">
        <AnimatePresence mode="wait">
          <motion.div
            key={active ?? 'default'}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="flex items-center gap-2 text-sm"
          >
            {active !== null ? (
              <>
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: PHASES[active].color }} />
                <span className="font-medium text-[var(--ink)]">{PHASES[active].label}</span>
                <span className="text-[var(--ink-subtle)]">
                  — {PHASES[active].min}–{PHASES[active].max}% of the timeline
                </span>
              </>
            ) : (
              <span className="text-[var(--ink-subtle)]">Hover or tab through a phase for its share of the timeline.</span>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5">
        {PHASES.map((phase, i) => (
          <div key={phase.label} className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)]">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: phase.color }} />
            {i + 1}. {phase.label}
          </div>
        ))}
      </div>
    </div>
  );
}
