import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calendar,
  Clock,
  Users,
  Workflow,
  ArrowRight,
  SlidersHorizontal,
  Database,
  Layers,
  Table2,
  Gauge,
  AlertTriangle,
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

/**
 * Which constraint actually binds the migration window. At a few hundred tables
 * this is almost always the people doing code conversion. At tens of thousands
 * it is usually neither bytes nor people -- it is per-object API throughput and
 * the fixed ceremony each wave carries. Surfacing which one binds is the point:
 * adding engineers to a clone-bound migration buys nothing.
 */
export type Bottleneck = 'objects' | 'bytes' | 'code' | 'waves' | 'none';

export interface ScaleBreakdown {
  waves: number;
  tablesPerWave: number;
  effectiveWorkers: number;
  tablesPerHour: number;
  objectBoundWeeks: number;
  byteBoundWeeks: number;
  codeBoundWeeks: number;
  waveOverheadWeeks: number;
  transferHours: number;
  manualJobs: number;
  bottleneck: Bottleneck;
}

/**
 * Scale inputs. All optional so the pre-scale call signature keeps working --
 * `tableCount: 0` means "not modelled" and falls back to the original
 * volume-only heuristic.
 */
export interface ScaleInputs {
  tableCount?: number;
  catalogCount?: number;
  /** Accelerator concurrency: databricks-replicator `concurrency.max_workers`,
   *  or the thread pool in a hand-rolled clone loop. */
  parallelWorkers?: number;
  /** MEASURED effective cross-cloud throughput, not the advertised link rate. */
  throughputGbps?: number;
  /** Tables per wave. Wave count is what turns a fast clone into a long program. */
  tablesPerWave?: number;
}

interface Calculated {
  phases: PhaseResult[];
  totalWeeks: number;
  scale: ScaleBreakdown | null;
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

// ---------------------------------------------------------------------------
// Scale constants. Every one of these is a PLANNING DEFAULT to be replaced with
// a number measured during the pilot -- the runbook's own instruction is
// "measure, don't assume" (see /execution/large-scale-data-transfer). They are
// named and exported so a reader can see exactly what the model assumed.
// ---------------------------------------------------------------------------

/** Wall-clock per table for one worker, end to end: DEEP CLONE (metadata + file
 *  copy), grant replay, then the reconciliation query. A table is never one API
 *  call. The accelerated figure assumes a maintained accelerator batching and
 *  retrying these (databricks-replicator, workspace-migration); the manual
 *  figure assumes a hand-rolled loop with per-table review. */
export const SECONDS_PER_TABLE_ACCELERATED = 45;
export const SECONDS_PER_TABLE_MANUAL = 180;

/** Unity Catalog and cloud storage APIs rate-limit per account, so worker count
 *  buys throughput linearly only until the limit binds, then flattens hard.
 *  Modelled as a saturating exponential rather than a linear speedup, with the
 *  ceiling set to databricks-replicator's own validated range for
 *  `concurrency.max_workers` (1-64, default 8 -- confirmed directly against
 *  config/models.py, not the README). "Scale worker count to the source
 *  cloud's actual per-account API rate limit, not to an arbitrary bigger-is-
 *  faster instinct" -- /execution/large-scale-data-transfer. Note this is a
 *  within-catalog ceiling only: the same tool processes catalogs strictly
 *  sequentially, so raising this past 64 buys nothing and adding catalogs
 *  does not add parallelism the way adding workers does. */
export const WORKER_SATURATION_CEILING = 64;

/** Bulk migration runs in scheduled windows against a live source, not 24/7. */
export const MIGRATION_HOURS_PER_WEEK = 60;

/** Object listing, retries, and the small-file penalty. Same factor the
 *  transfer-time formula on /execution/large-scale-data-transfer uses. */
export const TRANSFER_OVERHEAD_FACTOR = 1.35;

/** Fixed ceremony per wave regardless of its size: scope freeze, reconciliation
 *  gate, owner sign-off. This is what makes a 50k-table estate a multi-quarter
 *  program even when the clone itself finishes in days. */
export const WAVE_OVERHEAD_WEEKS_ACCELERATED = 0.6;
export const WAVE_OVERHEAD_WEEKS_MANUAL = 1.0;

/** Jobs deploy in bulk (Asset Bundles, Terraform exporter). What costs calendar
 *  time is the fraction that cannot be mechanically translated -- file-arrival
 *  triggers backed by cloud-native event sources, cross-cloud node types,
 *  hardcoded workspace ids. See /pipelines/workflows-jobs. */
export const MANUAL_JOB_FRACTION_ACCELERATED = 0.12;
export const MANUAL_JOB_FRACTION_MANUAL = 0.35;

/** How many non-mechanical jobs one engineer re-maps and smoke-tests per week. */
export const JOBS_REVIEWED_PER_ENGINEER_WEEK = 12;

export const DEFAULT_TABLES_PER_WAVE = 2500;

interface SliderConfig {
  key: string;
  label: string;
  icon: React.ElementType;
  min: number;
  max: number;
  step: number;
  unit: string;
  hint?: string;
}

// Ranges sized for a mid-to-large estate: tens of catalogs, tens of thousands of
// tables, thousands of jobs. The previous ceilings (20 workspaces / 2k notebooks
// / 200 jobs) could not express an estate this size at all.
const SLIDERS: SliderConfig[] = [
  { key: 'workspaceCount', label: 'Workspaces', icon: Workflow, min: 1, max: 60, step: 1, unit: '' },
  { key: 'catalogCount', label: 'Catalogs', icon: Layers, min: 1, max: 100, step: 1, unit: '', hint: 'Each carries its own external locations, credentials and grant design' },
  { key: 'tableCount', label: 'Tables', icon: Table2, min: 0, max: 100000, step: 500, unit: '', hint: 'The number that decides the window past ~10k. 0 disables the throughput model' },
  { key: 'userCount', label: 'Users', icon: Users, min: 5, max: 5000, step: 5, unit: '' },
  { key: 'notebookCount', label: 'Notebooks', icon: Calendar, min: 10, max: 20000, step: 50, unit: '' },
  { key: 'jobCount', label: 'Jobs', icon: Workflow, min: 5, max: 10000, step: 25, unit: '' },
  { key: 'dataVolumeTB', label: 'Data volume', icon: Database, min: 1, max: 10000, step: 5, unit: ' TB' },
  { key: 'teamSize', label: 'Team size', icon: Users, min: 2, max: 40, step: 1, unit: ' people' },
  { key: 'parallelWorkers', label: 'Parallel workers', icon: Gauge, min: 1, max: 128, step: 1, unit: '', hint: 'Accelerator concurrency (replicator max_workers). Saturates against API rate limits' },
  { key: 'throughputGbps', label: 'Measured throughput', icon: Gauge, min: 1, max: 100, step: 1, unit: ' Gbps', hint: 'Pilot-measured effective rate, not the advertised link' },
  { key: 'tablesPerWave', label: 'Tables per wave', icon: Layers, min: 250, max: 20000, step: 250, unit: '', hint: 'Fewer tables per wave means more waves, and every wave carries fixed ceremony' },
];

interface Preset {
  label: string;
  workspaceCount: number;
  catalogCount: number;
  tableCount: number;
  userCount: number;
  notebookCount: number;
  jobCount: number;
  dataVolumeTB: number;
  teamSize: number;
  parallelWorkers: number;
  throughputGbps: number;
  tablesPerWave: number;
  aiAccelerated: boolean;
}

// Grounded in: Databricks' own Lakebridge claims (2x faster / timelines cut in half /
// 80% less manual effort -- databricks.com/blog "Introducing Lakebridge" and "New migrations,
// faster and more predictable"), a partner case study claiming 30-40% reduction via GenAI
// automation (Zensar ZenseAI.Data), and industry lift-and-shift benchmarks (2-4 months for
// mid-size scope; enterprise data warehouses with years of accumulated logic still commonly
// run 6-18 months even with tooling). See the "Sources" note below the results.
const PRESETS: Preset[] = [
  { label: 'Pilot', workspaceCount: 1, catalogCount: 2, tableCount: 200, userCount: 5, notebookCount: 20, jobCount: 5, dataVolumeTB: 1, teamSize: 3, parallelWorkers: 4, throughputGbps: 5, tablesPerWave: 250, aiAccelerated: true },
  { label: 'Small', workspaceCount: 1, catalogCount: 4, tableCount: 1500, userCount: 10, notebookCount: 50, jobCount: 20, dataVolumeTB: 5, teamSize: 3, parallelWorkers: 4, throughputGbps: 5, tablesPerWave: 750, aiAccelerated: true },
  { label: 'Medium', workspaceCount: 5, catalogCount: 10, tableCount: 8000, userCount: 100, notebookCount: 400, jobCount: 250, dataVolumeTB: 50, teamSize: 6, parallelWorkers: 8, throughputGbps: 8, tablesPerWave: 1500, aiAccelerated: true },
  { label: 'Large (25 catalogs, 50k tables, 4k jobs)', workspaceCount: 12, catalogCount: 25, tableCount: 50000, userCount: 1200, notebookCount: 6000, jobCount: 4000, dataVolumeTB: 900, teamSize: 12, parallelWorkers: 16, throughputGbps: 10, tablesPerWave: 2500, aiAccelerated: true },
  { label: 'Large, no accelerators', workspaceCount: 12, catalogCount: 25, tableCount: 50000, userCount: 1200, notebookCount: 6000, jobCount: 4000, dataVolumeTB: 900, teamSize: 12, parallelWorkers: 4, throughputGbps: 10, tablesPerWave: 2500, aiAccelerated: false },
  { label: 'Very large (30 catalogs, 80k tables)', workspaceCount: 30, catalogCount: 40, tableCount: 80000, userCount: 3000, notebookCount: 12000, jobCount: 7500, dataVolumeTB: 3000, teamSize: 20, parallelWorkers: 32, throughputGbps: 20, tablesPerWave: 4000, aiAccelerated: true },
];

function ceil(val: number): number {
  return Math.ceil(val);
}

function round1(val: number): number {
  return Math.round(val * 10) / 10;
}

/**
 * Workers bought vs workers that actually do work, against the API rate limit.
 * Exported so the UI can show the gap -- requesting 64 workers when 32 is the
 * ceiling is the single most common over-estimate in a bulk migration plan.
 */
export function effectiveWorkers(requested: number): number {
  const w = Math.max(1, requested);
  return WORKER_SATURATION_CEILING * (1 - Math.exp(-w / WORKER_SATURATION_CEILING));
}

/**
 * The byte-bound window, using the same formula published on
 * /execution/large-scale-data-transfer so the tool and the runbook cannot drift:
 *   hours = (TB * 8 * 1024 * overhead) / (Gbps * 3600)
 */
export function transferHours(dataVolumeTB: number, throughputGbps: number): number {
  const gbps = Math.max(0.1, throughputGbps);
  return (dataVolumeTB * 8 * 1024 * TRANSFER_OVERHEAD_FACTOR) / (gbps * 3600);
}

export function computeTimeline(
  workspaceCount: number,
  userCount: number,
  notebookCount: number,
  jobCount: number,
  teamSize: number,
  cloudPair: CloudPair,
  aiAccelerated: boolean = false,
  dataVolumeTB: number = 10,
  scale: ScaleInputs = {},
): Calculated {
  const crossCloud = cloudPair !== 'same-cloud';

  // Team size has diminishing returns, not linear ones -- doubling a migration squad
  // doesn't halve the calendar time (coordination overhead, review bottlenecks, shared
  // environments). Modeled as a square-root scale against a 4-person baseline: a 2-person
  // team runs ~41% longer, a 12-person team compresses to ~58% of baseline, not 33%.
  // Applied only to phases real headcount actually parallelizes -- not foundation
  // (architectural, largely sequential) or cutover (a calendar event, not a backlog).
  const baselineTeam = 4;
  const teamFactor = Math.sqrt(baselineTeam / Math.max(teamSize, 1));

  const tableCount = Math.max(0, scale.tableCount ?? 0);
  const catalogCount = Math.max(0, scale.catalogCount ?? 0);
  const scaleModelled = tableCount > 0;

  // Data volume drives its own line of effort independent of notebook/job counts --
  // moving and reconciling 800TB takes real wall-clock time regardless of how few
  // pipelines touch it. Log-scaled since transfer/validation throughput scales with
  // parallel workers and bandwidth, not linearly with raw TB. Used only when no
  // table count is supplied; with one, the physical model below replaces it rather
  // than stacking on top of it.
  const volumeWeeksRaw = scaleModelled ? 0 : Math.log10(dataVolumeTB + 1);

  // --- The physical model, when a table count is supplied ------------------
  //
  // Three independent constraints, and the migration window is the WORST of
  // them plus per-wave ceremony -- not their sum. Bytes move while people
  // convert code; they do not queue behind each other.
  const workers = effectiveWorkers(scale.parallelWorkers ?? (aiAccelerated ? 8 : 3));
  const secondsPerTable = aiAccelerated ? SECONDS_PER_TABLE_ACCELERATED : SECONDS_PER_TABLE_MANUAL;
  const tablesPerHour = (3600 / secondsPerTable) * workers;
  const objectBoundWeeks = scaleModelled
    ? tableCount / tablesPerHour / MIGRATION_HOURS_PER_WEEK
    : 0;

  const hours = transferHours(dataVolumeTB, scale.throughputGbps ?? (crossCloud ? 8 : 20));
  const byteBoundWeeks = scaleModelled ? hours / MIGRATION_HOURS_PER_WEEK : 0;

  // Code conversion is the only one of the three that responds to team size.
  const codeBoundWeeks = scaleModelled
    ? ((notebookCount / (aiAccelerated ? 150 : 75)) + (jobCount / (aiAccelerated ? 400 : 160))) *
      teamFactor
    : 0;

  const tablesPerWave = Math.max(100, scale.tablesPerWave ?? DEFAULT_TABLES_PER_WAVE);
  const waves = scaleModelled ? Math.max(1, Math.ceil(tableCount / tablesPerWave)) : 0;
  const waveOverheadWeeks =
    waves * (aiAccelerated ? WAVE_OVERHEAD_WEEKS_ACCELERATED : WAVE_OVERHEAD_WEEKS_MANUAL);

  // Jobs do not migrate one at a time at this scale -- a bundle or Terraform
  // plan deploys them in bulk. The calendar cost is the non-mechanical fraction.
  const manualJobs = Math.round(
    jobCount * (aiAccelerated ? MANUAL_JOB_FRACTION_ACCELERATED : MANUAL_JOB_FRACTION_MANUAL),
  );

  const discovery = aiAccelerated
    ? ceil(Math.max(1, (0.5 + workspaceCount * 0.25 + userCount / 150 + catalogCount / 20) * teamFactor))
    : ceil(Math.max(2, (1 + workspaceCount * 0.5 + userCount / 100 + catalogCount / 10) * teamFactor));
  // Each catalog carries its own external locations, storage credential bindings,
  // workspace bindings and grant design -- foundation work that does not compress
  // with headcount because it is architectural.
  const foundation = aiAccelerated
    ? ceil((crossCloud ? 2.5 : 1.5) + workspaceCount * 0.25 + catalogCount * 0.1)
    : ceil((crossCloud ? 3 : 2) + workspaceCount * 0.3 + catalogCount * 0.15);

  const legacyMigration = aiAccelerated
    ? Math.max(1.5, (0.5 + notebookCount / 150 + jobCount / 70 + workspaceCount * 0.25) * teamFactor + volumeWeeksRaw * 0.8)
    : Math.max(3, (1 + notebookCount / 75 + jobCount / 40 + workspaceCount * 0.5) * teamFactor + volumeWeeksRaw * 1.5);
  const migration = scaleModelled
    ? ceil(
        Math.max(objectBoundWeeks, byteBoundWeeks, codeBoundWeeks) +
          waveOverheadWeeks +
          workspaceCount * (aiAccelerated ? 0.15 : 0.3),
      )
    : ceil(legacyMigration);

  const legacyPipelines = aiAccelerated
    ? Math.max(1, (0.5 + jobCount / 55 + notebookCount / 180) * teamFactor)
    : Math.max(2, (1 + jobCount / 30 + notebookCount / 100) * teamFactor);
  const pipelines = scaleModelled
    ? ceil(
        Math.max(
          1,
          (aiAccelerated ? 1 : 2) +
            (manualJobs / JOBS_REVIEWED_PER_ENGINEER_WEEK) * teamFactor +
            notebookCount / (aiAccelerated ? 400 : 180) * teamFactor,
        ),
      )
    : ceil(legacyPipelines);

  // Reconciling 50k tables is itself an object-throughput problem, not a
  // headcount one -- the checksum queries run at the warehouse's pace.
  const validation = aiAccelerated
    ? ceil(Math.max(1.5, (0.7 + userCount / 130 + workspaceCount * 0.22) * teamFactor + volumeWeeksRaw * 0.3 + objectBoundWeeks * 0.35))
    : ceil(Math.max(2, (1 + userCount / 100 + workspaceCount * 0.3) * teamFactor + volumeWeeksRaw * 0.5 + objectBoundWeeks * 0.5));
  // Cutover is a calendar event per wave, not a backlog -- more waves means more
  // freeze windows to run, each with its own drain and sign-off.
  const cutover = aiAccelerated
    ? ceil(Math.max(1, 0.8 + workspaceCount * 0.25 + waves * 0.05))
    : ceil(Math.max(1, 1 + workspaceCount * 0.3 + waves * 0.08));
  const hypercare = scaleModelled
    ? ceil(Math.max(aiAccelerated ? 1 : 2, waves * (aiAccelerated ? 0.08 : 0.12)))
    : (aiAccelerated ? 1 : 2);

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

  let breakdown: ScaleBreakdown | null = null;
  if (scaleModelled) {
    const worst = Math.max(objectBoundWeeks, byteBoundWeeks, codeBoundWeeks);
    let bottleneck: Bottleneck = 'none';
    if (waveOverheadWeeks > worst) bottleneck = 'waves';
    else if (worst === objectBoundWeeks) bottleneck = 'objects';
    else if (worst === byteBoundWeeks) bottleneck = 'bytes';
    else bottleneck = 'code';
    breakdown = {
      waves,
      tablesPerWave,
      effectiveWorkers: round1(workers),
      tablesPerHour: Math.round(tablesPerHour),
      objectBoundWeeks: round1(objectBoundWeeks),
      byteBoundWeeks: round1(byteBoundWeeks),
      codeBoundWeeks: round1(codeBoundWeeks),
      waveOverheadWeeks: round1(waveOverheadWeeks),
      transferHours: Math.round(hours),
      manualJobs,
      bottleneck,
    };
  }

  return { phases, totalWeeks, scale: breakdown };
}

const BOTTLENECK_COPY: Record<Bottleneck, { title: string; detail: string }> = {
  objects: {
    title: 'Per-object throughput is the constraint',
    detail:
      'The window is set by how many tables per hour the pipeline can clone, grant and reconcile — not by bytes and not by headcount. Adding engineers does not move this number; adding accelerator workers does, until the API rate limit binds. Raise concurrency, and cut wave count before cutting scope.',
  },
  bytes: {
    title: 'Raw transfer bandwidth is the constraint',
    detail:
      'More tables per hour will not help — the bytes cannot move faster over this path. Fix the pipe before the schedule: a private interconnect or a transfer appliance, procured during Foundation, not Cutover.',
  },
  code: {
    title: 'Code conversion is the constraint',
    detail:
      'The estate is small enough that machines finish before people do. This is the one bottleneck that responds to team size and to AI-assisted conversion — the data path has spare capacity.',
  },
  waves: {
    title: 'Wave ceremony is the constraint',
    detail:
      'The clone finishes fast; the program does not. Every wave carries a scope freeze, a reconciliation gate and an owner sign-off regardless of how many tables it holds. At this table count the fixed cost per wave outweighs the moving of data — widen the waves, or accept that the calendar is governance, not engineering.',
  },
  none: { title: 'No single constraint dominates', detail: 'Object throughput, bandwidth and code conversion are within range of each other.' },
};

export default function TimelineEstimator() {
  const [workspaceCount, setWorkspaceCount] = useState(12);
  const [catalogCount, setCatalogCount] = useState(25);
  const [tableCount, setTableCount] = useState(50000);
  const [userCount, setUserCount] = useState(1200);
  const [notebookCount, setNotebookCount] = useState(6000);
  const [jobCount, setJobCount] = useState(4000);
  const [dataVolumeTB, setDataVolumeTB] = useState(900);
  const [teamSize, setTeamSize] = useState(12);
  const [parallelWorkers, setParallelWorkers] = useState(16);
  const [throughputGbps, setThroughputGbps] = useState(10);
  const [tablesPerWave, setTablesPerWave] = useState(2500);
  const [cloudPair, setCloudPair] = useState<CloudPair>('azure-aws');
  const [aiAccelerated, setAiAccelerated] = useState(true);
  const [calculated, setCalculated] = useState<Calculated | null>(null);

  const handleCalculate = useCallback(() => {
    const result = computeTimeline(
      workspaceCount, userCount, notebookCount, jobCount, teamSize, cloudPair, aiAccelerated, dataVolumeTB,
      { tableCount, catalogCount, parallelWorkers, throughputGbps, tablesPerWave },
    );
    setCalculated(result);
  }, [workspaceCount, userCount, notebookCount, jobCount, teamSize, cloudPair, aiAccelerated, dataVolumeTB, tableCount, catalogCount, parallelWorkers, throughputGbps, tablesPerWave]);

  const applyPreset = useCallback((p: Preset) => {
    setWorkspaceCount(p.workspaceCount);
    setCatalogCount(p.catalogCount);
    setTableCount(p.tableCount);
    setUserCount(p.userCount);
    setNotebookCount(p.notebookCount);
    setJobCount(p.jobCount);
    setDataVolumeTB(p.dataVolumeTB);
    setTeamSize(p.teamSize);
    setParallelWorkers(p.parallelWorkers);
    setThroughputGbps(p.throughputGbps);
    setTablesPerWave(p.tablesPerWave);
    setAiAccelerated(p.aiAccelerated);
  }, []);

  const sliders = [
    { value: workspaceCount, setter: setWorkspaceCount, config: SLIDERS[0] },
    { value: catalogCount, setter: setCatalogCount, config: SLIDERS[1] },
    { value: tableCount, setter: setTableCount, config: SLIDERS[2] },
    { value: userCount, setter: setUserCount, config: SLIDERS[3] },
    { value: notebookCount, setter: setNotebookCount, config: SLIDERS[4] },
    { value: jobCount, setter: setJobCount, config: SLIDERS[5] },
    { value: dataVolumeTB, setter: setDataVolumeTB, config: SLIDERS[6] },
    { value: teamSize, setter: setTeamSize, config: SLIDERS[7] },
    { value: parallelWorkers, setter: setParallelWorkers, config: SLIDERS[8] },
    { value: throughputGbps, setter: setThroughputGbps, config: SLIDERS[9] },
    { value: tablesPerWave, setter: setTablesPerWave, config: SLIDERS[10] },
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
                {config.hint && (
                  <span className="text-xs leading-snug text-[var(--ink-subtle)]">{config.hint}</span>
                )}
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

          <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2.5">
            <input
              type="checkbox"
              checked={aiAccelerated}
              onChange={(e) => setAiAccelerated(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--accent)]"
            />
            <span className="text-sm">
              <span className="font-medium text-[var(--ink)]">AI-accelerated tooling</span>
              <span className="block text-xs text-[var(--ink-muted)]">
                UCX, Lakebridge, and GenAI-assisted code conversion -- discounts discovery,
                data/pipeline migration, and validation effort. Off models a traditional,
                no-tooling migration for comparison.
              </span>
            </span>
          </label>

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

                {/* What actually binds the window */}
                {calculated.scale && (
                  <div className="mt-5 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
                      <AlertTriangle className="h-4 w-4 text-[var(--accent)]" />
                      {BOTTLENECK_COPY[calculated.scale.bottleneck].title}
                    </div>
                    <p className="mb-3 text-xs leading-relaxed text-[var(--ink-muted)]">
                      {BOTTLENECK_COPY[calculated.scale.bottleneck].detail}
                    </p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
                      {[
                        ['Waves', `${calculated.scale.waves} x ${calculated.scale.tablesPerWave.toLocaleString()} tables`],
                        ['Wave ceremony', `${calculated.scale.waveOverheadWeeks} wk`],
                        ['Object-bound', `${calculated.scale.objectBoundWeeks} wk`],
                        ['Byte-bound', `${calculated.scale.byteBoundWeeks} wk (${calculated.scale.transferHours.toLocaleString()} h)`],
                        ['Code-bound', `${calculated.scale.codeBoundWeeks} wk`],
                        ['Throughput', `${calculated.scale.tablesPerHour.toLocaleString()} tables/h`],
                        ['Effective workers', `${calculated.scale.effectiveWorkers} of ${parallelWorkers}`],
                        ['Jobs needing hands', `${calculated.scale.manualJobs.toLocaleString()} of ${jobCount.toLocaleString()}`],
                      ].map(([label, value]) => (
                        <div key={label} className="flex flex-col">
                          <span className="text-[var(--ink-subtle)]">{label}</span>
                          <span className="font-semibold text-[var(--ink)]">{value}</span>
                        </div>
                      ))}
                    </div>
                    {calculated.scale.effectiveWorkers < parallelWorkers * 0.75 && (
                      <p className="mt-3 border-t border-[var(--border)] pt-3 text-xs leading-relaxed text-[var(--ink-muted)]">
                        Only {calculated.scale.effectiveWorkers} of the {parallelWorkers} requested
                        workers do useful work — Unity Catalog and cloud storage APIs rate-limit per
                        account, so past roughly {WORKER_SATURATION_CEILING} the extra workers earn
                        retries, not throughput.
                      </p>
                    )}
                  </div>
                )}

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

      <p className="mt-6 text-xs leading-relaxed text-[var(--ink-subtle)]">
        <strong className="text-[var(--ink-muted)]">How the scale model works.</strong> Past a
        table count, the window is the <em>worst</em> of three independent constraints — per-object
        throughput, raw bandwidth, and code conversion — plus fixed ceremony per wave. Not their
        sum: bytes move while people convert code. Only the code term responds to team size; a
        clone-bound migration does not go faster because more engineers joined. Worker concurrency
        saturates against Unity Catalog and cloud storage API rate limits rather than scaling
        linearly. The transfer term uses the same formula published on{' '}
        <a href="/execution/large-scale-data-transfer" className="underline hover:text-[var(--accent)]">
          large-scale data transfer
        </a>{' '}
        (TB × 8 × 1024 × 1.35 ÷ Gbps ÷ 3600) so the tool and the runbook cannot drift apart. Jobs
        are treated as bulk-deployable (Asset Bundles, Terraform exporter) with only a
        non-mechanical fraction — file-arrival triggers, cross-cloud node types, hardcoded
        workspace ids — costing calendar time. Per-table seconds, the worker ceiling, and per-wave
        overhead are <strong className="text-[var(--ink-muted)]">planning defaults to replace with
        your own pilot measurements</strong>; the runbook's own instruction is measure, don't
        assume. Estates far outside the published benchmark range (tens of thousands of tables,
        thousands of jobs) extrapolate beyond any cited case study — treat the traditional
        comparison as a directional contrast, not a forecast.
        <br /><br />
        Sources: Databricks —{' '}
        <a href="https://www.databricks.com/blog/introducing-lakebridge-free-open-data-migration-databricks-sql" target="_blank" rel="noopener noreferrer" className="underline hover:text-[var(--accent)]">
          Introducing Lakebridge
        </a>{' '}
        (timelines cut in half, ~80% less manual conversion effort) and{' '}
        <a href="https://www.databricks.com/blog/new-migrations-faster-and-more-predictable" target="_blank" rel="noopener noreferrer" className="underline hover:text-[var(--accent)]">
          New migrations, faster and more predictable
        </a>
        . Industry lift-and-shift benchmarks (2–4 months for mid-size scope) and enterprise
        data-warehouse baselines (6–18 months for large, long-accumulated estates) are used
        for the traditional (non-accelerated) comparison. Treat every number here as a
        planning estimate to pressure-test against your own discovery findings, not a quote.
      </p>
    </motion.div>
  );
}
