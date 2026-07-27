import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

const APPLIES: string[] = [
  'A new consumer needs read access to data that lives in another cloud',
  'A merger/acquisition needs a unified catalog across two estates on different clouds',
  'A compliance program needs centralized audit/lineage without disturbing data residency',
  'Leadership has mandated "get everything on one cloud" without a clear technical reason',
];

const DOES_NOT_APPLY: string[] = [
  'Compute needs sustained low-latency co-location with the data',
  'Egress cost of repeated cross-cloud reads exceeds one-time migration cost',
  'A hard data-residency requirement that federation cannot satisfy',
];

export default function ApplicabilityCompare() {
  return (
    <div className="my-6 grid gap-4 sm:grid-cols-2">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-4">
        <h4 className="mb-3 flex items-center gap-2 font-semibold text-[var(--ink)]">
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          Evaluate this decision when
        </h4>
        <ul className="space-y-2 text-sm text-[var(--ink-muted)]">
          {APPLIES.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-emerald-500">•</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-elevated)] p-4">
        <h4 className="mb-3 flex items-center gap-2 font-semibold text-[var(--ink)]">
          <XCircle className="h-4 w-4 text-[var(--ink-subtle)]" />
          Skip it when a genuine technical driver exists
        </h4>
        <ul className="space-y-2 text-sm text-[var(--ink-muted)]">
          {DOES_NOT_APPLY.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-[var(--ink-subtle)]">•</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
