import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  X,
  Filter,
  SlidersHorizontal,
  ArrowUpDown,
  Check,
} from 'lucide-react';
import CloudLogo from './CloudLogo.tsx';
import instanceData from '../data/instanceTypes.json';

interface InstanceType {
  cloud: 'aws' | 'azure' | 'gcp';
  family: string;
  name: string;
  vCpu: number;
  memoryGb: number;
  gpu: number | null;
  gpuType: string | null;
  databricksSku: string;
  tier: string;
  category: string;
}

type Cloud = 'aws' | 'azure' | 'gcp';
type SortKey = 'name' | 'vCpu' | 'memoryGb' | 'gpu';
type SortDir = 'asc' | 'desc';

const TIERS = Array.from(new Set(instanceData.map((d) => d.tier))).sort();
const MAX_VCPU = Math.max(...instanceData.map((d) => d.vCpu));

const CLOUD_OPTIONS: { value: Cloud | 'all'; label: string }[] = [
  { value: 'all', label: 'All clouds' },
  { value: 'aws', label: 'AWS' },
  { value: 'azure', label: 'Azure' },
  { value: 'gcp', label: 'GCP' },
];

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'vCpu', label: 'vCPU' },
  { key: 'memoryGb', label: 'Memory' },
  { key: 'gpu', label: 'GPU' },
];

export default function InstanceTypeMapper() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCloud, setSelectedCloud] = useState<Cloud | 'all'>('all');
  const [minVcpu, setMinVcpu] = useState(0);
  const [selectedTier, setSelectedTier] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [selectedNames, setSelectedNames] = useState<Set<string>>(new Set());

  const data = instanceData as InstanceType[];

  const tiers = useMemo(() => TIERS, []);
  const maxVcpu = useMemo(() => MAX_VCPU, []);

  const filtered = useMemo(() => {
    let result = [...data];

    if (selectedCloud !== 'all') {
      result = result.filter((d) => d.cloud === selectedCloud);
    }

    if (selectedTier !== 'all') {
      result = result.filter((d) => d.tier === selectedTier);
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (d) =>
          d.name.toLowerCase().includes(q) ||
          d.family.toLowerCase().includes(q) ||
          d.databricksSku.toLowerCase().includes(q)
      );
    }

    if (minVcpu > 0) {
      result = result.filter((d) => d.vCpu >= minVcpu);
    }

    result.sort((a, b) => {
      const aVal = a[sortKey] ?? 0;
      const bVal = b[sortKey] ?? 0;
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });

    return result;
  }, [data, selectedCloud, selectedTier, searchQuery, minVcpu, sortKey, sortDir]);

  const comparisonRows = useMemo(
    () => data.filter((d) => selectedNames.has(d.name)),
    [data, selectedNames]
  );

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  function toggleSelected(name: string) {
    setSelectedNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  function resetFilters() {
    setSearchQuery('');
    setSelectedCloud('all');
    setMinVcpu(0);
    setSelectedTier('all');
    setSortKey('name');
    setSortDir('asc');
  }

  const hasFilters =
    searchQuery || selectedCloud !== 'all' || minVcpu > 0 || selectedTier !== 'all';

  function SortIcon({ columnKey }: { columnKey: SortKey }) {
    const active = sortKey === columnKey;
    return (
      <ArrowUpDown
        className={`ml-1 inline h-3.5 w-3.5 transition-transform ${
          active ? 'text-[var(--accent)]' : 'text-[var(--ink-subtle)]'
        } ${active && sortDir === 'desc' ? 'rotate-180' : ''}`}
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8"
    >
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="mb-2 flex items-center gap-2 text-2xl font-semibold text-[var(--ink)]">
            <Filter className="h-6 w-6 text-[var(--accent)]" />
            Cloud Instance Type Mapper
          </h2>
          <p className="max-w-2xl text-[var(--ink-muted)]">
            Browse and compare Databricks instance types across AWS, Azure, and GCP by spec, tier, and category.
          </p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="mb-5 grid gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 md:grid-cols-[1fr_auto_auto_auto_auto] md:items-center">
        {/* Search */}
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--ink-subtle)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search name, family, or SKU…"
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] py-2 pl-9 pr-3 text-sm text-[var(--ink)] outline-none ring-[var(--accent)] placeholder:text-[var(--ink-subtle)] focus:ring-2"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-[var(--ink-subtle)] hover:text-[var(--ink)]"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Cloud dropdown */}
        <select
          value={selectedCloud}
          onChange={(e) => setSelectedCloud(e.target.value as Cloud | 'all')}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm text-[var(--ink)] outline-none ring-[var(--accent)] focus:ring-2"
        >
          {CLOUD_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Tier dropdown */}
        <select
          value={selectedTier}
          onChange={(e) => setSelectedTier(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm text-[var(--ink)] outline-none ring-[var(--accent)] focus:ring-2"
        >
          <option value="all">All tiers</option>
          {tiers.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        {/* vCPU range */}
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 shrink-0 text-[var(--ink-subtle)]" />
          <input
            type="range"
            min={0}
            max={maxVcpu}
            step={4}
            value={minVcpu}
            onChange={(e) => setMinVcpu(Number(e.target.value))}
            className="h-1.5 w-24 cursor-pointer appearance-none rounded-full bg-[var(--border)] accent-[var(--accent)]"
            title={`Min vCPU: ${minVcpu}`}
          />
          <span className="min-w-[3rem] text-xs font-medium tabular-nums text-[var(--ink-muted)]">
            {minVcpu > 0 ? `≥${minVcpu}` : 'Any'}
          </span>
        </div>

        {/* Reset */}
        {hasFilters && (
          <motion.button
            onClick={resetFilters}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-medium text-[var(--ink-muted)] transition-colors hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
          >
            <X className="h-4 w-4" />
            Reset
          </motion.button>
        )}
      </div>

      {/* Results count */}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-[var(--ink-muted)]">
          <span className="font-semibold text-[var(--ink)]">{filtered.length}</span>{' '}
          {filtered.length === 1 ? 'instance type' : 'instance types'} found
        </span>
        {selectedNames.size > 0 && (
          <button
            onClick={() => setSelectedNames(new Set())}
            className="text-xs font-medium text-[var(--ink-subtle)] hover:text-[var(--ink)]"
          >
            Clear selection ({selectedNames.size})
          </button>
        )}
      </div>

      {/* Comparison section */}
      <AnimatePresence>
        {comparisonRows.length >= 2 && (
          <motion.div
            key="comparison"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="mb-6 overflow-hidden"
          >
            <div className="rounded-xl border border-[var(--accent)]/40 bg-[var(--accent-soft)] p-4">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--accent)]">
                <Filter className="h-4 w-4" />
                Comparing {comparisonRows.length} instance types
              </h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {comparisonRows.map((row) => (
                  <div
                    key={row.name}
                    className="rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] p-3 text-sm"
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <CloudLogo cloud={row.cloud} size="sm" />
                      <span className="font-medium text-[var(--ink)]">{row.name}</span>
                    </div>
                    <div className="space-y-1 text-[var(--ink-muted)]">
                      <div className="flex justify-between">
                        <span className="text-[var(--ink-subtle)]">vCPU</span>
                        <span className="font-medium text-[var(--ink)]">{row.vCpu}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--ink-subtle)]">Memory</span>
                        <span className="font-medium text-[var(--ink)]">{row.memoryGb} GB</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--ink-subtle)]">GPU</span>
                        <span className="font-medium text-[var(--ink)]">
                          {row.gpu ? `${row.gpu}× ${row.gpuType}` : '—'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--ink-subtle)]">SKU</span>
                        <span className="font-medium text-[var(--ink)]">{row.databricksSku}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[var(--ink-subtle)]">Tier</span>
                        <span className="font-medium text-[var(--ink)]">{row.tier}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => toggleSelected(row.name)}
                      className="mt-2 w-full rounded border border-[var(--border)] py-1 text-xs text-[var(--ink-subtle)] transition-colors hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              <th className="w-10 px-3 py-3">
                <span className="sr-only">Select</span>
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Cloud
              </th>
              {COLUMNS.map((col) => (
                <th key={col.key} className="px-3 py-3">
                  <button
                    onClick={() => toggleSort(col.key)}
                    className="inline-flex items-center text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)] hover:text-[var(--ink)]"
                  >
                    {col.label}
                    <SortIcon columnKey={col.key} />
                  </button>
                </th>
              ))}
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Family
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                DB SKU
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Tier
              </th>
              <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Category
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-6 py-16 text-center">
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="flex flex-col items-center gap-2"
                  >
                    <Search className="h-8 w-8 text-[var(--ink-subtle)]" />
                    <p className="font-medium text-[var(--ink)]">No instance types found</p>
                    <p className="text-sm text-[var(--ink-muted)]">
                      Try adjusting your filters or search query.
                    </p>
                    {hasFilters && (
                      <button
                        onClick={resetFilters}
                        className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
                      >
                        Reset filters
                      </button>
                    )}
                  </motion.div>
                </td>
              </tr>
            ) : (
              filtered.map((row, idx) => {
                const isSelected = selectedNames.has(row.name);
                return (
                  <motion.tr
                    key={row.name}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.012 }}
                    className={`cursor-pointer border-b border-[var(--border)] transition-colors last:border-0 hover:bg-[var(--surface-hover)] ${
                      isSelected ? 'bg-[var(--accent-soft)]' : ''
                    }`}
                    onClick={() => toggleSelected(row.name)}
                  >
                    <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                      <span
                        className={`inline-flex h-4 w-4 items-center justify-center rounded border ${
                          isSelected
                            ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                            : 'border-[var(--border)] bg-[var(--surface-elevated)]'
                        }`}
                      >
                        {isSelected && <Check className="h-3 w-3" />}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <CloudLogo cloud={row.cloud} size="sm" />
                    </td>
                    <td className="px-3 py-2.5 font-medium text-[var(--ink)]">{row.name}</td>
                    <td className="px-3 py-2.5 tabular-nums text-[var(--ink)]">{row.vCpu}</td>
                    <td className="px-3 py-2.5 tabular-nums text-[var(--ink)]">
                      {row.memoryGb} GB
                    </td>
                    <td className="px-3 py-2.5 text-[var(--ink)]">
                      {row.gpu ? (
                        <span className="tabular-nums">
                          {row.gpu}× {row.gpuType}
                        </span>
                      ) : (
                        <span className="text-[var(--ink-subtle)]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-[var(--ink-muted)]">{row.family}</td>
                    <td className="px-3 py-2.5">
                      <span className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-xs font-medium text-[var(--ink)]">
                        {row.databricksSku}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          row.tier === 'GPU'
                            ? 'bg-violet-500/10 text-violet-400'
                            : row.tier === 'Memory'
                              ? 'bg-blue-500/10 text-blue-400'
                              : row.tier === 'Compute'
                                ? 'bg-amber-500/10 text-amber-400'
                                : row.tier === 'Storage'
                                  ? 'bg-emerald-500/10 text-emerald-400'
                                  : 'bg-gray-500/10 text-gray-400'
                        }`}
                      >
                        {row.tier}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`text-xs font-medium ${
                          row.category === 'Premium'
                            ? 'text-amber-400'
                            : 'text-[var(--ink-muted)]'
                        }`}
                      >
                        {row.category}
                      </span>
                    </td>
                  </motion.tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
