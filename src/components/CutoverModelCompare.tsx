import React from 'react';

type Level = 'Low' | 'Medium' | 'High';

interface Model {
  name: string;
  downtime: string;
  risk: Level;
  cost: Level;
  useCase: string;
}

const LEVEL_COLOR: Record<Level, string> = {
  Low: '#10B981',
  Medium: '#F59E0B',
  High: '#EF4444',
};

const MODELS: Model[] = [
  { name: 'Big-bang', downtime: 'Hours to days', risk: 'High', cost: 'Low', useCase: 'Small estate, tolerant users' },
  { name: 'Incremental', downtime: 'Minimal', risk: 'Medium', cost: 'Medium', useCase: 'Large tables, daily sync' },
  { name: 'Blue-green', downtime: 'Near-zero', risk: 'Low', cost: 'High', useCase: 'Mission-critical workloads' },
];

function LevelPill({ level }: { level: Level }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{ background: `${LEVEL_COLOR[level]}1A`, color: LEVEL_COLOR[level] }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: LEVEL_COLOR[level] }} />
      {level}
    </span>
  );
}

export default function CutoverModelCompare() {
  return (
    <div className="my-6 grid gap-4 sm:grid-cols-3">
      {MODELS.map((m) => (
        <div key={m.name} className="rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-4">
          <h4 className="mb-3 font-semibold text-[var(--ink)]">{m.name}</h4>
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-[var(--ink-subtle)]">Downtime</dt>
              <dd className="font-medium text-[var(--ink)]">{m.downtime}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-[var(--ink-subtle)]">Risk</dt>
              <dd><LevelPill level={m.risk} /></dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-[var(--ink-subtle)]">Cost</dt>
              <dd><LevelPill level={m.cost} /></dd>
            </div>
          </dl>
          <p className="mt-3 border-t border-[var(--border)] pt-3 text-xs text-[var(--ink-muted)]">{m.useCase}</p>
        </div>
      ))}
    </div>
  );
}
