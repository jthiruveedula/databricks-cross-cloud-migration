import React, { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DollarSign,
  TrendingUp,
  Database,
  Cpu,
  Network,
  RefreshCw,
  Calculator,
  BarChart3,
} from 'lucide-react';

type Cloud = 'aws' | 'azure' | 'gcp';
type WorkloadType = 'jobs' | 'allPurpose' | 'sqlServerless';

interface CloudRates {
  /** underlying cloud VM cost, $/node-hour */
  compute: number;
  /** blob storage, $/GB-month */
  storage: number;
  /** egress, $/GB */
  transfer: number;
}

// Underlying cloud infrastructure rates (VM + storage + egress), not Databricks' own fee.
// Illustrative on-demand list-price order of magnitude, mid-2026 — verify against each
// cloud's current pricing calculator before using for a real budget.
const CLOUD_RATES: Record<Cloud, CloudRates> = {
  aws: { compute: 0.55, storage: 0.023, transfer: 0.09 },
  azure: { compute: 0.52, storage: 0.0208, transfer: 0.087 },
  gcp: { compute: 0.49, storage: 0.02, transfer: 0.085 },
};

// Databricks Unit (DBU) list price, $/DBU, Premium tier — billed by Databricks on top of
// the cloud infra cost above (two separate bills on AWS/GCP; consolidated on Azure).
// Rates are broadly consistent across clouds; sources: Flexera, CloudZero, Cloudchipr,
// OpsLyft 2026 Databricks pricing guides. Re-verify against the live Databricks pricing
// page before using for a real budget — these are list prices, not your negotiated rate.
const DBU_RATES: Record<WorkloadType, number> = {
  jobs: 0.15,
  allPurpose: 0.55,
  sqlServerless: 0.7,
};

const WORKLOAD_LABELS: Record<WorkloadType, string> = {
  jobs: 'Jobs Compute',
  allPurpose: 'All-Purpose Compute',
  sqlServerless: 'SQL Serverless',
};

// Cloud infra typically runs 30-60% on top of the DBU charge (rule of thumb from the
// same pricing guides) — used only as a sanity-check caption, not in the formula itself.
const GB_PER_TB = 1000;

const CLOUD_LABELS: Record<Cloud, string> = {
  aws: 'AWS',
  azure: 'Azure',
  gcp: 'GCP',
};

const CLOUD_COLORS: Record<Cloud, { text: string; bg: string; border: string; bar: string }> = {
  aws: { text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20', bar: 'bg-orange-500/20' },
  azure: { text: 'text-sky-400', bg: 'bg-sky-500/10', border: 'border-sky-500/20', bar: 'bg-sky-500/20' },
  gcp: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', bar: 'bg-emerald-500/20' },
};

interface CostBreakdown {
  compute: number;
  dbu: number;
  storage: number;
  transfer: number;
  total: number;
}

interface Params {
  clusterCount: number;
  nodesPerCluster: number;
  computeHoursPerDay: number;
  storageTb: number;
  dataTransferGb: number;
  gpuWorkload: boolean;
  workloadType: WorkloadType;
}

export function estimateCost(cloud: Cloud, params: Params): CostBreakdown {
  const rates = CLOUD_RATES[cloud];
  const gpuMultiplier = params.gpuWorkload ? 2.5 : 1;
  const totalComputeUnits = params.clusterCount * params.nodesPerCluster;
  const monthlyHours = params.computeHoursPerDay * 30;
  const nodeHours = totalComputeUnits * monthlyHours * gpuMultiplier;
  const compute = Math.round(nodeHours * rates.compute);
  const dbu = Math.round(nodeHours * DBU_RATES[params.workloadType]);
  const storage = Math.round(params.storageTb * GB_PER_TB * rates.storage);
  const transfer = Math.round(params.dataTransferGb * rates.transfer);
  const total = compute + dbu + storage + transfer;
  return { compute, dbu, storage, transfer, total };
}

export function formatCurrency(n: number): string {
  return '$' + n.toLocaleString('en-US');
}

export default function CostCalculator() {
  const [clusterCount, setClusterCount] = useState(5);
  const [nodesPerCluster, setNodesPerCluster] = useState(3);
  const [computeHoursPerDay, setComputeHoursPerDay] = useState(8);
  const [storageTb, setStorageTb] = useState(50);
  const [dataTransferGb, setDataTransferGb] = useState(500);
  const [gpuWorkload, setGpuWorkload] = useState(false);
  const [workloadType, setWorkloadType] = useState<WorkloadType>('allPurpose');
  const [calculated, setCalculated] = useState(false);

  const params: Params = useMemo(
    () => ({
      clusterCount,
      nodesPerCluster,
      computeHoursPerDay,
      storageTb,
      dataTransferGb,
      gpuWorkload,
      workloadType,
    }),
    [clusterCount, nodesPerCluster, computeHoursPerDay, storageTb, dataTransferGb, gpuWorkload, workloadType],
  );

  const results = useMemo(() => {
    if (!calculated) return null;
    return {
      aws: estimateCost('aws', params),
      azure: estimateCost('azure', params),
      gcp: estimateCost('gcp', params),
    };
  }, [calculated, params]);

  const winner = useMemo(() => {
    if (!results) return null;
    return (['aws', 'azure', 'gcp'] as Cloud[]).reduce((a, b) =>
      results[a].total < results[b].total ? a : b,
    );
  }, [results]);

  const maxTotal = useMemo(() => {
    if (!results) return 0;
    return Math.max(results.aws.total, results.azure.total, results.gcp.total);
  }, [results]);

  const savings = useMemo(() => {
    if (!results) return null;
    const totals = [results.aws.total, results.azure.total, results.gcp.total];
    return Math.max(...totals) - Math.min(...totals);
  }, [results]);

  const worst = useMemo(() => {
    if (!results) return null;
    return (['aws', 'azure', 'gcp'] as Cloud[]).reduce((a, b) =>
      results[a].total > results[b].total ? a : b,
    );
  }, [results]);

  const handleCalculate = useCallback(() => setCalculated(true), []);
  const handleReset = useCallback(() => {
    setClusterCount(5);
    setNodesPerCluster(3);
    setComputeHoursPerDay(8);
    setStorageTb(50);
    setDataTransferGb(500);
    setGpuWorkload(false);
    setWorkloadType('allPurpose');
    setCalculated(false);
  }, []);

  const clouds: Cloud[] = ['aws', 'azure', 'gcp'];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8"
    >
      {/* ── Header ── */}
      <div className="mb-6">
        <h2 className="mb-2 flex items-center gap-2 text-2xl font-semibold text-[var(--ink)]">
          <Calculator className="h-6 w-6 text-[var(--accent)]" />
          Cloud Cost Comparison Calculator
        </h2>
        <p className="text-[var(--ink-muted)]">
          Estimate Databricks infrastructure costs across clouds.
        </p>
      </div>

      {/* ── Form panel ── */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
        <div className="mb-6 grid gap-5 sm:grid-cols-2">
          {/* Clusters */}
          <div>
            <label className="mb-1.5 flex items-center justify-between text-sm font-medium text-[var(--ink)]">
              <span className="flex items-center gap-1.5">
                <Cpu className="h-4 w-4 text-[var(--ink-muted)]" />
                Clusters
              </span>
              <span className="text-[var(--accent)]">{clusterCount}</span>
            </label>
            <input
              type="range"
              min={1}
              max={50}
              value={clusterCount}
              onChange={(e) => setClusterCount(Number(e.target.value))}
              className="w-full accent-[var(--accent)]"
            />
            <div className="mt-0.5 flex justify-between text-xs text-[var(--ink-subtle)]">
              <span>1</span>
              <span>50</span>
            </div>
          </div>

          {/* Nodes per cluster */}
          <div>
            <label className="mb-1.5 flex items-center justify-between text-sm font-medium text-[var(--ink)]">
              <span className="flex items-center gap-1.5">
                <Database className="h-4 w-4 text-[var(--ink-muted)]" />
                Nodes / cluster
              </span>
              <span className="text-[var(--accent)]">{nodesPerCluster}</span>
            </label>
            <input
              type="range"
              min={1}
              max={20}
              value={nodesPerCluster}
              onChange={(e) => setNodesPerCluster(Number(e.target.value))}
              className="w-full accent-[var(--accent)]"
            />
            <div className="mt-0.5 flex justify-between text-xs text-[var(--ink-subtle)]">
              <span>1</span>
              <span>20</span>
            </div>
          </div>

          {/* Hours / day */}
          <div>
            <label className="mb-1.5 flex items-center justify-between text-sm font-medium text-[var(--ink)]">
              <span className="flex items-center gap-1.5">
                <TrendingUp className="h-4 w-4 text-[var(--ink-muted)]" />
                Hours / day
              </span>
              <span className="text-[var(--accent)]">{computeHoursPerDay}</span>
            </label>
            <input
              type="range"
              min={1}
              max={24}
              value={computeHoursPerDay}
              onChange={(e) => setComputeHoursPerDay(Number(e.target.value))}
              className="w-full accent-[var(--accent)]"
            />
            <div className="mt-0.5 flex justify-between text-xs text-[var(--ink-subtle)]">
              <span>1</span>
              <span>24</span>
            </div>
          </div>

          {/* Storage (TB) */}
          <div>
            <label className="mb-1.5 flex items-center justify-between text-sm font-medium text-[var(--ink)]">
              <span className="flex items-center gap-1.5">
                <Database className="h-4 w-4 text-[var(--ink-muted)]" />
                Storage (TB)
              </span>
              <span className="text-[var(--accent)]">{storageTb}</span>
            </label>
            <input
              type="range"
              min={1}
              max={500}
              value={storageTb}
              onChange={(e) => setStorageTb(Number(e.target.value))}
              className="w-full accent-[var(--accent)]"
            />
            <div className="mt-0.5 flex justify-between text-xs text-[var(--ink-subtle)]">
              <span>1</span>
              <span>500</span>
            </div>
          </div>

          {/* Data transfer (GB) */}
          <div>
            <label className="mb-1.5 flex items-center justify-between text-sm font-medium text-[var(--ink)]">
              <span className="flex items-center gap-1.5">
                <Network className="h-4 w-4 text-[var(--ink-muted)]" />
                Data transfer (GB)
              </span>
              <span className="text-[var(--accent)]">{dataTransferGb.toLocaleString()}</span>
            </label>
            <input
              type="range"
              min={0}
              max={10000}
              value={dataTransferGb}
              onChange={(e) => setDataTransferGb(Number(e.target.value))}
              className="w-full accent-[var(--accent)]"
            />
            <div className="mt-0.5 flex justify-between text-xs text-[var(--ink-subtle)]">
              <span>0</span>
              <span>10,000</span>
            </div>
          </div>

          {/* Workload type (drives DBU rate) */}
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-[var(--ink)]">
              <Cpu className="h-4 w-4 text-[var(--ink-muted)]" />
              Compute type
            </label>
            <select
              value={workloadType}
              onChange={(e) => setWorkloadType(e.target.value as WorkloadType)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm text-[var(--ink)]"
            >
              {(Object.keys(WORKLOAD_LABELS) as WorkloadType[]).map((w) => (
                <option key={w} value={w}>
                  {WORKLOAD_LABELS[w]} (${DBU_RATES[w].toFixed(2)}/DBU)
                </option>
              ))}
            </select>
          </div>

          {/* GPU toggle */}
          <div className="flex items-center">
            <label className="flex cursor-pointer items-center gap-3 text-sm font-medium text-[var(--ink)]">
              <button
                type="button"
                role="switch"
                aria-checked={gpuWorkload}
                onClick={() => setGpuWorkload((p) => !p)}
                className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border border-[var(--border)] transition-colors ${
                  gpuWorkload ? 'bg-[var(--accent)]' : 'bg-[var(--surface-elevated)]'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                    gpuWorkload ? 'translate-x-[1.35rem]' : 'translate-x-[0.15rem]'
                  }`}
                />
              </button>
              GPU workload (2.5&times; compute)
            </label>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex flex-wrap gap-3">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleCalculate}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-6 py-2.5 font-medium text-white shadow-glow transition-shadow hover:shadow-glow"
          >
            <Calculator className="h-4 w-4" />
            Calculate Costs
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleReset}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-5 py-2.5 font-medium text-[var(--ink)] transition-colors hover:bg-[var(--surface-hover)]"
          >
            <RefreshCw className="h-4 w-4" />
            Reset
          </motion.button>
        </div>
      </div>

      {/* ── Results ── */}
      <AnimatePresence>
        {calculated && results && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 16 }}
            transition={{ duration: 0.4 }}
            className="mt-8"
          >
            {/* 3-column cost breakdown */}
            <div className="mb-6 grid gap-4 md:grid-cols-3">
              {clouds.map((cloud, idx) => {
                const cost = results[cloud];
                const isWinner = winner === cloud;
                const colors = CLOUD_COLORS[cloud];
                return (
                  <motion.div
                    key={cloud}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className={`relative overflow-hidden rounded-xl border ${colors.border} ${colors.bg} p-5`}
                  >
                    {isWinner && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                        className="absolute right-3 top-3 rounded-full bg-emerald-500 px-2.5 py-0.5 text-xs font-bold text-white"
                      >
                        Best
                      </motion.div>
                    )}
                    <h3 className={`mb-3 text-lg font-bold ${colors.text}`}>
                      <DollarSign className="mr-1 inline-block h-4 w-4" />
                      {CLOUD_LABELS[cloud]}
                    </h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between text-[var(--ink)]">
                        <span className="text-[var(--ink-muted)]">Compute (cloud infra)</span>
                        <span className="font-medium">{formatCurrency(cost.compute)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[var(--ink)]">
                        <span className="text-[var(--ink-muted)]">Databricks DBU</span>
                        <span className="font-medium">{formatCurrency(cost.dbu)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[var(--ink)]">
                        <span className="text-[var(--ink-muted)]">Storage</span>
                        <span className="font-medium">{formatCurrency(cost.storage)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[var(--ink)]">
                        <span className="text-[var(--ink-muted)]">Transfer</span>
                        <span className="font-medium">{formatCurrency(cost.transfer)}</span>
                      </div>
                      <div className="border-t border-[var(--border)] pt-2">
                        <div className="flex items-center justify-between text-base font-bold text-[var(--ink)]">
                          <span>Total / mo</span>
                          <span className={isWinner ? 'text-emerald-400' : ''}>
                            {formatCurrency(cost.total)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            {/* Horizontal bar chart comparison */}
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mb-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5"
            >
              <h4 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
                <BarChart3 className="h-4 w-4 text-[var(--accent)]" />
                Monthly total comparison
              </h4>
              <div className="space-y-3">
                {clouds.map((cloud) => {
                  const cost = results[cloud];
                  const isWinner = winner === cloud;
                  const colors = CLOUD_COLORS[cloud];
                  const pct = maxTotal > 0 ? (cost.total / maxTotal) * 100 : 0;
                  return (
                    <div key={cloud} className="flex items-center gap-3">
                      <span className={`w-12 text-right text-sm font-semibold ${colors.text}`}>
                        {CLOUD_LABELS[cloud]}
                      </span>
                      <div className="flex-1">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max(pct, 12)}%` }}
                          transition={{ duration: 0.6, ease: 'easeOut' }}
                          className={`flex h-7 items-center justify-end rounded-md px-2 ${
                            isWinner
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : `${colors.bar} ${colors.text}`
                          }`}
                        >
                          <span className="text-xs font-semibold">
                            {formatCurrency(cost.total)}
                          </span>
                        </motion.div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>

            {/* Savings hint */}
            {winner && worst && savings !== null && savings > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4"
              >
                <p className="flex items-center gap-2 text-sm font-medium text-emerald-400">
                  <TrendingUp className="h-4 w-4" />
                  Moving from {CLOUD_LABELS[worst]} to {CLOUD_LABELS[winner]} could save{' '}
                  <span className="font-bold">{formatCurrency(savings)}</span>/mo
                </p>
              </motion.div>
            )}

            <p className="mt-4 text-xs text-[var(--ink-subtle)]">
              Estimate only: cloud infra rates + Databricks {WORKLOAD_LABELS[workloadType]} DBU list price, mid-2026
              order of magnitude. Excludes reserved/committed-use discounts, storage tiering, and negotiated
              Enterprise pricing (typically 15–25% above Premium). On AWS/GCP, cloud infra and DBU are billed
              separately; Azure consolidates them. Verify current rates on the{' '}
              <a
                href="https://www.databricks.com/product/pricing"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                Databricks pricing page
              </a>{' '}
              before budgeting.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
