import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calendar,
  Clock,
  Users,
  Workflow,
  ArrowRight,
  SlidersHorizontal,
} from 'lucide-react';

type CloudPair =
  | 'same-cloud'
  | 'azure-aws'
  | 'azure-gcp'
  | 'aws-azure'
  | 'aws-gcp'
  | 'gcp-azure'
  | 'gcp-aws';

interface PhaseResult {
  key: string;
  label: string;
  weeks: number;
  color: string;
}

interface Calculated {
  phases: PhaseResult[];
  totalWeeks: number;
}

const CLOUD_PAIR_LABELS: Record<CloudPair, string> = {
  'same-cloud': 'Same cloud (lift & shift)',
  'azure-aws': 'Azure → AWS',
  'azure-gcp': 'Azure → GCP',
  'aws-azure': 'AWS → Azure',
  'aws-gcp': 'AWS → GCP',
  'gcp-azure': 'GCP → Azure',
  'gcp-aws': 'GCP → AWS',
};

const PHASE_META: Record<string, { label: string; color: string }> = {
  discovery: { label: 'Discovery', color: '#8B5CF6' },
  foundation: { label: 'Foundation', color: '#3B82F6' },
  migration: { label: 'Data & Compute Migration', color: '#10B981' },
  pipelines: { label: 'Pipeline Migration', color: '#F59E0B' },
  validation: { label: 'Validation', color: '#F97316' },
  cutover: { label: 'Cutover', color: '#EF4444' },
  hypercare: { label: 'Hypercare', color: '#EC4899' },
};

interface SliderConfig {
  key: string;
  label: string;
  icon: React.ElementType;
  min: number;
  max: number;
  step: number;
  unit: string;
}

const SLIDERS: SliderConfig[] = [
  { key: 'workspaceCount', label: 'Workspaces', icon: Workflow, min: 1, max: 20, step: 1, unit: '' },
  { key: 'userCount', label: 'Users', icon: Users, min: 5, max: 500, step: 5, unit: '' },
  { key: 'notebookCount', label: 'Notebooks', icon: Calendar, min: 10, max: 2000, step: 10, unit: '' },
  { key: 'jobCount', label: 'Jobs', icon: Workflow, min: 5, max: 200, step: 5, unit: '' },
  { key: 'teamSize', label: 'Team size', icon: Users, min: 2, max: 15, step: 1, unit: ' people' },
];

interface Preset {
  label: string;
  workspaceCount: number;
  userCount: number;
  notebookCount: number;
  jobCount: number;
  teamSize: number;
}

const PRESETS: Preset[] = [
  { label: 'Small (1 ws, 10 users)', workspaceCount: 1, userCount: 10, notebookCount: 50, jobCount: 10, teamSize: 3 },
  { label: 'Medium (5 ws, 100 users)', workspaceCount: 5, userCount: 100, notebookCount: 400, jobCount: 60, teamSize: 6 },
  { label: 'Large (20 ws, 500 users)', workspaceCount: 20, userCount: 500, notebookCount: 1500, jobCount: 150, teamSize: 12 },
];

function ceil(val: number): number {
  return Math.ceil(val);
}

function computeTimeline(
  workspaceCount: number,
  userCount: number,
  notebookCount: number,
  jobCount: number,
  _teamSize: number,
  cloudPair: CloudPair,
): Calculated {
  const crossCloud = cloudPair !== 'same-cloud';

  const discovery = ceil(Math.max(2, 1 + workspaceCount * 0.5 + userCount / 100));
  const foundation = ceil((crossCloud ? 3 : 2) + workspaceCount * 0.3);
  const migration = ceil(Math.max(3, 1 + notebookCount / 75 + jobCount / 40 + workspaceCount * 0.5));
  const pipelines = ceil(Math.max(2, 1 + jobCount / 30 + notebookCount / 100));
  const validation = ceil(Math.max(2, 1 + userCount / 100 + workspaceCount * 0.3));
  const cutover = ceil(Math.max(1, 1 + workspaceCount * 0.3));
  const hypercare = 2;

  const phases: PhaseResult[] = [
    { key: 'discovery', label: PHASE_META.discovery.label, weeks: discovery, color: PHASE_META.discovery.color },
    { key: 'foundation', label: PHASE_META.foundation.label, weeks: foundation, color: PHASE_META.foundation.color },
    { key: 'migration', label: PHASE_META.migration.label, weeks: migration, color: PHASE_META.migration.color },
    { key: 'pipelines', label: PHASE_META.pipelines.label, weeks: pipelines, color: PHASE_META.pipelines.color },
    { key: 'validation', label: PHASE_META.validation.label, weeks: validation, color: PHASE_META.validation.color },
    { key: 'cutover', label: PHASE_META.cutover.label, weeks: cutover, color: PHASE_META.cutover.color },
    { key: 'hypercare', label: PHASE_META.hypercare.label, weeks: hypercare, color: PHASE_META.hypercare.color },
  ];

  const totalWeeks = phases.reduce((sum, p) => sum + p.weeks, 0);

  return { phases, totalWeeks };
}

export default function TimelineEstimator() {
  const [workspaceCount, setWorkspaceCount] = useState(3);
  const [userCount, setUserCount] = useState(50);
  const [notebookCount, setNotebookCount] = useState(100);
  const [jobCount, setJobCount] = useState(30);
  const [teamSize, setTeamSize] = useState(4);
  const [cloudPair, setCloudPair] = useState<CloudPair>('azure-aws');
  const [calculated, setCalculated] = useState<Calculated | null>(null);

  const handleCalculate = useCallback(() => {
    const result = computeTimeline(workspaceCount, userCount, notebookCount, jobCount, teamSize, cloudPair);
    setCalculated(result);
  }, [workspaceCount, userCount, notebookCount, jobCount, teamSize, cloudPair]);

  const applyPreset = useCallback((p: Preset) => {
    setWorkspaceCount(p.workspaceCount);
    setUserCount(p.userCount);
    setNotebookCount(p.notebookCount);
    setJobCount(p.jobCount);
    setTeamSize(p.teamSize);
  }, []);

  const sliders = [
    { value: workspaceCount, setter: setWorkspaceCount, config: SLIDERS[0] },
    { value: userCount, setter: setUserCount, config: SLIDERS[1] },
    { value: notebookCount, setter: setNotebookCount, config: SLIDERS[2] },
    { value: jobCount, setter: setJobCount, config: SLIDERS[3] },
    { value: teamSize, setter: setTeamSize, config: SLIDERS[4] },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8"
    >
      <div className="mb-6">
        <h2 className="mb-2 flex items-center gap-2 text-2xl font-semibold text-[var(--ink)]">
          <Clock className="h-6 w-6 text-[var(--accent)]" />
          Migration Timeline Estimator
        </h2>
        <p className="max-w-2xl text-[var(--ink-muted)]">
          Estimate phase-by-phase duration for your migration.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* Config panel */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
            <SlidersHorizontal className="h-4 w-4 text-[var(--accent)]" />
            Configuration
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            {sliders.map(({ value, setter, config }) => (
              <label key={config.key} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1.5 text-[var(--ink)]">
                    <config.icon className="h-3.5 w-3.5 text-[var(--ink-muted)]" />
                    {config.label}
                  </span>
                  <span className="rounded-md bg-[var(--accent-soft)] px-2 py-0.5 text-xs font-semibold text-[var(--accent)]">
                    {value}{config.unit}
                  </span>
                </div>
                <input
                  type="range"
                  min={config.min}
                  max={config.max}
                  step={config.step}
                  value={value}
                  onChange={(e) => setter(Number(e.target.value))}
                  className="h-2 w-full cursor-pointer appearance-none rounded-full bg-[var(--border)] outline-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[var(--accent)] [&::-webkit-slider-thumb]:shadow-md"
                />
                <div className="flex justify-between text-xs text-[var(--ink-subtle)]">
                  <span>{config.min}</span>
                  <span>{config.max}</span>
                </div>
              </label>
            ))}
          </div>

          <div className="mt-5 flex flex-col gap-2">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="flex items-center gap-1.5 font-medium text-[var(--ink)]">
                <Workflow className="h-3.5 w-3.5 text-[var(--ink-muted)]" />
                Cloud pair
              </span>
              <select
                value={cloudPair}
                onChange={(e) => setCloudPair(e.target.value as CloudPair)}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm text-[var(--ink)] outline-none ring-[var(--accent)] focus:ring-2"
              >
                {(Object.keys(CLOUD_PAIR_LABELS) as CloudPair[]).map((pair) => (
                  <option key={pair} value={pair}>
                    {CLOUD_PAIR_LABELS[pair]}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-[var(--ink-muted)]">Presets:</span>
            {PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => applyPreset(p)}
                className="rounded-full border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1 text-xs font-medium text-[var(--ink-muted)] transition-colors hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
              >
                {p.label}
              </button>
            ))}
          </div>

          <motion.button
            onClick={handleCalculate}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent)] px-5 py-2.5 font-medium text-white shadow-glow transition-shadow hover:shadow-glow"
          >
            Calculate Timeline <ArrowRight className="h-4 w-4" />
          </motion.button>
        </div>

        {/* Results panel */}
        <div className="min-h-[300px]">
          <AnimatePresence mode="wait">
            {calculated ? (
              <motion.div
                key="results"
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 16 }}
                transition={{ duration: 0.4 }}
                className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5"
              >
                <div className="mb-4 flex items-baseline gap-2">
                  <span className="text-2xl font-bold text-[var(--ink)]">{calculated.totalWeeks} weeks</span>
                  <span className="text-sm text-[var(--ink-muted)]">
                    (~{Math.round(calculated.totalWeeks / 4.33)} months)
                  </span>
                </div>

                <div className="space-y-3">
                  {calculated.phases.map((phase, idx) => {
                    const startWeek =
                      idx === 0
                        ? 1
                        : calculated.phases.slice(0, idx).reduce((s, p) => s + p.weeks, 0) + 1;
                    const endWeek = startWeek + phase.weeks - 1;
                    const pct = (phase.weeks / calculated.totalWeeks) * 100;

                    return (
                      <motion.div
                        key={phase.key}
                        initial={{ opacity: 0, x: -16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.07, duration: 0.35 }}
                        className="flex flex-col gap-1"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-[var(--ink)]">{phase.label}</span>
                          <span className="text-[var(--ink-subtle)]">
                            W{startWeek} → W{endWeek}
                          </span>
                        </div>
                        <div className="relative h-5 w-full overflow-hidden rounded-full bg-[var(--surface-elevated)]">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ delay: idx * 0.07 + 0.2, duration: 0.6, ease: 'easeOut' }}
                            style={{
                              background: `linear-gradient(90deg, ${phase.color}, ${phase.color}dd)`,
                            }}
                            className="h-full rounded-full"
                          />
                        </div>
                        <div className="text-right text-xs text-[var(--ink-subtle)]">
                          {phase.weeks} wk{phase.weeks > 1 ? 's' : ''}
                        </div>
                      </motion.div>
                    );
                  })}
                </div>

                {/* Color key */}
                <div className="mt-5 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-[var(--border)] pt-4">
                  {calculated.phases.map((phase) => (
                    <div key={phase.key} className="flex items-center gap-1.5 text-xs text-[var(--ink-muted)]">
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: phase.color }}
                      />
                      {phase.label}: {phase.weeks} wk
                    </div>
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="placeholder"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex h-full min-h-[300px] items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-5"
              >
                <div className="text-center">
                  <Calendar className="mx-auto mb-3 h-10 w-10 text-[var(--ink-subtle)]" />
                  <p className="text-sm text-[var(--ink-muted)]">
                    Adjust inputs and click <span className="font-medium text-[var(--ink)]">Calculate Timeline</span> to see your migration estimate.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
