import React, { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus,
  X,
  Download,
  RefreshCw,
  Table,
  Users,
  Minus,
} from 'lucide-react';

type RaciValue = 'R' | 'A' | 'C' | 'I' | null;
type Matrix = Record<string, Record<string, RaciValue>>;

const PREDEFINED_PHASES = [
  'Discovery',
  'Cloud Mapping',
  'Governance Setup',
  'Security Hardening',
  'Compute Migration',
  'Pipeline Migration',
  'Analytics Migration',
  'ML Migration',
  'Data Validation',
  'Integration Testing',
  'Cutover',
  'Hypercare',
];

const RACI_META: Record<string, { bg: string; text: string; label: string }> = {
  R: { bg: 'bg-blue-500/10', text: 'text-blue-400', label: 'Responsible' },
  A: { bg: 'bg-amber-500/10', text: 'text-amber-400', label: 'Accountable' },
  C: { bg: 'bg-purple-500/10', text: 'text-purple-400', label: 'Consulted' },
  I: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', label: 'Informed' },
};

const CYCLE: RaciValue[] = [null, 'R', 'A', 'C', 'I'];

const DEFAULT_ROLES = ['Cloud Architect', 'Data Engineering', 'Security Engineering'];

function cycleValue(current: RaciValue): RaciValue {
  const idx = CYCLE.indexOf(current);
  return CYCLE[(idx + 1) % CYCLE.length];
}

function buildDefaultMatrix(): Matrix {
  const m: Matrix = {};
  const set = (phase: string, role: string, val: RaciValue) => {
    if (!m[phase]) m[phase] = {};
    m[phase][role] = val;
  };

  for (const phase of PREDEFINED_PHASES) {
    set(phase, 'Cloud Architect', null);
    set(phase, 'Data Engineering', null);
    set(phase, 'Security Engineering', null);
  }

  set('Discovery', 'Cloud Architect', 'A');
  set('Discovery', 'Data Engineering', 'R');
  set('Discovery', 'Security Engineering', 'C');

  set('Cloud Mapping', 'Cloud Architect', 'R');
  set('Cloud Mapping', 'Data Engineering', 'C');
  set('Cloud Mapping', 'Security Engineering', 'C');

  set('Governance Setup', 'Cloud Architect', 'A');
  set('Governance Setup', 'Data Engineering', 'I');
  set('Governance Setup', 'Security Engineering', 'R');

  set('Security Hardening', 'Cloud Architect', 'C');
  set('Security Hardening', 'Data Engineering', 'I');
  set('Security Hardening', 'Security Engineering', 'R');

  set('Compute Migration', 'Cloud Architect', 'C');
  set('Compute Migration', 'Data Engineering', 'R');
  set('Compute Migration', 'Security Engineering', 'I');

  set('Pipeline Migration', 'Cloud Architect', 'A');
  set('Pipeline Migration', 'Data Engineering', 'R');
  set('Pipeline Migration', 'Security Engineering', 'C');

  set('Analytics Migration', 'Cloud Architect', 'C');
  set('Analytics Migration', 'Data Engineering', 'R');
  set('Analytics Migration', 'Security Engineering', 'I');

  set('ML Migration', 'Cloud Architect', 'C');
  set('ML Migration', 'Data Engineering', 'R');
  set('ML Migration', 'Security Engineering', 'I');

  set('Data Validation', 'Cloud Architect', 'I');
  set('Data Validation', 'Data Engineering', 'R');
  set('Data Validation', 'Security Engineering', 'A');

  set('Integration Testing', 'Cloud Architect', 'A');
  set('Integration Testing', 'Data Engineering', 'R');
  set('Integration Testing', 'Security Engineering', 'C');

  set('Cutover', 'Cloud Architect', 'R');
  set('Cutover', 'Data Engineering', 'A');
  set('Cutover', 'Security Engineering', 'C');

  set('Hypercare', 'Cloud Architect', 'A');
  set('Hypercare', 'Data Engineering', 'R');
  set('Hypercare', 'Security Engineering', 'C');

  return m;
}

function generateCsv(phases: string[], roles: string[], matrix: Matrix): string {
  const header = ['Phase', ...roles];
  const rows = phases.map((phase) => [
    phase,
    ...roles.map((role) => matrix[phase]?.[role] ?? ''),
  ]);
  return [header.join(','), ...rows.map((r) => r.join(','))].join('\n');
}

function downloadCsv(csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'raci-matrix.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function RaciBuilder() {
  const [phases, setPhases] = useState<string[]>([...PREDEFINED_PHASES]);
  const [roles, setRoles] = useState<string[]>([...DEFAULT_ROLES]);
  const [matrix, setMatrix] = useState<Matrix>(buildDefaultMatrix);
  const [customPhaseInput, setCustomPhaseInput] = useState('');

  const updateMatrixCell = useCallback((phase: string, role: string) => {
    setMatrix((prev) => {
      const next = { ...prev };
      if (!next[phase]) next[phase] = {};
      next[phase] = { ...next[phase], [role]: cycleValue(next[phase][role] ?? null) };
      return next;
    });
  }, []);

  const addRole = useCallback(() => {
    const label = `Role ${roles.length + 1}`;
    setRoles((prev) => [...prev, label]);
    setMatrix((prev) => {
      const next = { ...prev };
      for (const phase of Object.keys(next)) {
        next[phase] = { ...next[phase], [label]: null };
      }
      return next;
    });
  }, [roles.length]);

  const removeRole = useCallback((role: string) => {
    setRoles((prev) => prev.filter((r) => r !== role));
    setMatrix((prev) => {
      const next = { ...prev };
      for (const phase of Object.keys(next)) {
        if (next[phase]) {
          const copy = { ...next[phase] };
          delete copy[role];
          next[phase] = copy;
        }
      }
      return next;
    });
  }, []);

  const updateRoleName = useCallback(
    (oldName: string, newName: string) => {
      const trimmed = newName.trim();
      if (!trimmed || trimmed === oldName) return;
      setRoles((prev) => {
        if (prev.includes(trimmed)) return prev;
        return prev.map((r) => (r === oldName ? trimmed : r));
      });
      setMatrix((prev) => {
        const next = { ...prev };
        for (const phase of Object.keys(next)) {
          if (next[phase] && oldName in next[phase]) {
            next[phase] = { ...next[phase], [trimmed]: next[phase][oldName] };
            const copy = { ...next[phase] };
            delete copy[oldName];
            next[phase] = copy;
          }
        }
        return next;
      });
    },
    [],
  );

  const addPhase = useCallback(
    (name: string) => {
      const trimmed = name.trim();
      if (!trimmed || phases.includes(trimmed)) return;
      setPhases((prev) => [...prev, trimmed]);
      setMatrix((prev) => {
        const next = { ...prev };
        next[trimmed] = Object.fromEntries(roles.map((r) => [r, null]));
        return next;
      });
      setCustomPhaseInput('');
    },
    [phases, roles],
  );

  const removePhase = useCallback((phase: string) => {
    setPhases((prev) => prev.filter((p) => p !== phase));
    setMatrix((prev) => {
      const next = { ...prev };
      delete next[phase];
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setPhases([...PREDEFINED_PHASES]);
    setRoles([...DEFAULT_ROLES]);
    setMatrix(buildDefaultMatrix());
    setCustomPhaseInput('');
  }, []);

  const csv = useMemo(() => generateCsv(phases, roles, matrix), [phases, roles, matrix]);

  const handleExport = useCallback(() => downloadCsv(csv), [csv]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-6 md:p-8"
    >
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="mb-2 flex items-center gap-2 text-2xl font-semibold text-[var(--ink)]">
            <Table className="h-6 w-6 text-[var(--accent)]" />
            RACI Matrix Builder
          </h2>
          <p className="max-w-2xl text-[var(--ink-muted)]">
            Assign Responsible, Accountable, Consulted, and Informed roles across
            migration phases. Click cells to cycle through values.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleExport}
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white shadow-glow transition-shadow hover:shadow-glow"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={reset}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2 text-sm font-medium text-[var(--ink-muted)] transition-colors hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
          >
            <RefreshCw className="h-4 w-4" />
            Reset
          </motion.button>
        </div>
      </div>

      {/* Legend */}
      <div className="mb-6 flex flex-wrap gap-4">
        {(['R', 'A', 'C', 'I'] as const).map((val) => (
          <div
            key={val}
            className="flex items-center gap-1.5 text-xs font-medium text-[var(--ink-muted)]"
          >
            <span
              className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold ${RACI_META[val].bg} ${RACI_META[val].text}`}
            >
              {val}
            </span>
            {RACI_META[val].label}
          </div>
        ))}
      </div>

      {/* Phases / Roles side-by-side on desktop */}
      <div className="mb-6 grid gap-6 md:grid-cols-2">
        {/* Migration Phases */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
            <Users className="h-4 w-4 text-[var(--accent)]" />
            Migration Phases
          </h3>
          <div className="mb-3 space-y-2">
            <AnimatePresence mode="popLayout">
              {phases.map((phase) => (
                <motion.div
                  key={phase}
                  layout
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10, scale: 0.95 }}
                  transition={{ duration: 0.18 }}
                  className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-2 text-sm text-[var(--ink)]"
                >
                  <span>{phase}</span>
                  <button
                    type="button"
                    onClick={() => removePhase(phase)}
                    className="rounded p-0.5 text-[var(--ink-subtle)] transition-colors hover:text-red-400"
                    aria-label={`Remove ${phase}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          <div className="flex gap-2">
            <input
              value={customPhaseInput}
              onChange={(e) => setCustomPhaseInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addPhase(customPhaseInput);
              }}
              placeholder="Add custom phase…"
              className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1.5 text-sm text-[var(--ink)] outline-none ring-[var(--accent)] placeholder:text-[var(--ink-subtle)] focus:ring-2"
            />
            <motion.button
              whileTap={{ scale: 0.95 }}
              type="button"
              onClick={() => addPhase(customPhaseInput)}
              disabled={!customPhaseInput.trim()}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            >
              <Plus className="h-3.5 w-3.5" />
              Add
            </motion.button>
          </div>
        </div>

        {/* Team Roles */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[var(--ink)]">
            <Users className="h-4 w-4 text-[var(--accent)]" />
            Team Roles
          </h3>
          <div className="mb-3 space-y-2">
            <AnimatePresence mode="popLayout">
              {roles.map((role) => (
                <motion.div
                  key={role}
                  layout
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10, scale: 0.95 }}
                  transition={{ duration: 0.18 }}
                  className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] px-3 py-1.5"
                >
                  <input
                    value={role}
                    onChange={(e) => updateRoleName(role, e.target.value)}
                    className="min-w-0 flex-1 bg-transparent text-sm text-[var(--ink)] outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => removeRole(role)}
                    className="rounded p-0.5 text-[var(--ink-subtle)] transition-colors hover:text-red-400"
                    aria-label={`Remove ${role}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          <motion.button
            whileTap={{ scale: 0.95 }}
            type="button"
            onClick={addRole}
            className="inline-flex items-center gap-1 rounded-lg border border-dashed border-[var(--border)] px-3 py-1.5 text-sm font-medium text-[var(--ink-muted)] transition-colors hover:border-[var(--accent)]/50 hover:text-[var(--accent)]"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Role
          </motion.button>
        </div>
      </div>

      {/* RACI Matrix Table */}
      <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
              <th className="sticky left-0 z-10 border-r border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Phase
              </th>
              {roles.map((role) => (
                <th
                  key={role}
                  className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-[var(--ink-muted)]"
                >
                  {role}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {phases.map((phase, idx) => (
              <motion.tr
                key={phase}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: idx * 0.025 }}
                className="border-b border-[var(--border)] last:border-b-0"
              >
                <td className="sticky left-0 z-10 border-r border-[var(--border)] bg-[var(--surface-elevated)] px-4 py-3 text-sm font-medium text-[var(--ink)]">
                  {phase}
                </td>
                {roles.map((role) => {
                  const value = matrix[phase]?.[role] ?? null;
                  const meta = value ? RACI_META[value] : null;
                  return (
                    <td key={role} className="px-2 py-2 text-center">
                      <motion.button
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        onClick={() => updateMatrixCell(phase, role)}
                        className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border text-sm font-bold transition-colors ${
                          meta
                            ? `${meta.bg} ${meta.text} border-transparent`
                            : 'border-[var(--border)] text-[var(--ink-subtle)] hover:border-[var(--accent)]/30'
                        }`}
                        aria-label={`${phase} — ${role}${value ? `: ${RACI_META[value].label}` : ': unset'}`}
                      >
                        {value ?? <Minus className="h-3.5 w-3.5" />}
                      </motion.button>
                    </td>
                  );
                })}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
